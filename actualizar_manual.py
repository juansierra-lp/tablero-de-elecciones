name: Scrape Registraduría - Resultados Electorales

# ============================================================
# CRON SCHEDULE
# GitHub Actions usa UTC. Colombia es UTC-5.
# Elecciones 31 may 2026, conteo activo desde ~5 PM (22:00 UTC).
# Programamos cada 30 minutos durante la ventana crítica.
# ============================================================
on:
  # Programación automática
  schedule:
    # Día E (31 mayo 2026): cada 30 min de 5 PM a 11:59 PM hora Colombia
    - cron: '*/30 22-23 31 5 *'   # 22:00-23:30 UTC = 5-6:30 PM Col (3 ejecuciones)
    - cron: '*/30 0-4 1 6 *'      # 0:00-4:30 UTC = 7-11:30 PM Col domingo (10 ejecuciones)
    # Día después (1 jun): cada 2 horas para capturar resultados finales
    - cron: '0 */2 1 6 *'
    # Segunda vuelta (21 jun 2026): mismo patrón
    - cron: '*/30 22-23 21 6 *'
    - cron: '*/30 0-4 22 6 *'

  # Disparo manual desde la pestaña Actions de GitHub
  workflow_dispatch:
    inputs:
      forzar:
        description: 'Forzar ejecución aunque no sea día electoral'
        required: false
        default: 'true'

jobs:
  scrape:
    runs-on: ubuntu-latest
    permissions:
      contents: write   # necesario para commitear cambios al repo

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Ejecutar scraper
        id: scrape
        run: |
          mkdir -p logs
          python3 scripts/scrape_registraduria.py 2>&1 | tee logs/last_run.log
          echo "exit_code=${PIPESTATUS[0]}" >> $GITHUB_OUTPUT
        continue-on-error: true

      - name: Detectar cambios
        id: cambios
        run: |
          if git diff --quiet datos.json; then
            echo "hay_cambios=false" >> $GITHUB_OUTPUT
            echo "✓ Sin cambios en datos.json"
          else
            echo "hay_cambios=true" >> $GITHUB_OUTPUT
            echo "✓ Detectados cambios en datos.json"
          fi

      - name: Commit y push si hay cambios
        if: steps.cambios.outputs.hay_cambios == 'true'
        run: |
          git config user.name "Dashboard Bot"
          git config user.email "bot@meli-dashboard.local"
          git add datos.json logs/
          git commit -m "🤖 Auto-update $(date -u +'%Y-%m-%d %H:%M UTC')"
          git push

      - name: Reportar resultado
        if: always()
        run: |
          echo "============================================"
          echo "Exit code del scraper: ${{ steps.scrape.outputs.exit_code }}"
          echo "Hay cambios: ${{ steps.cambios.outputs.hay_cambios }}"
          echo "============================================"
          if [ -f logs/last_run.log ]; then
            echo "--- Últimas 20 líneas del log ---"
            tail -n 20 logs/last_run.log
          fi

      - name: Subir log como artefacto (siempre)
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: scrape-log-${{ github.run_id }}
          path: logs/
          retention-days: 7
