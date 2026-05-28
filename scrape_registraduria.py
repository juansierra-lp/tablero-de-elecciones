name: Scraper de Noticias de Seguridad

# ============================================================
# Scrapea Google News RSS cada hora y actualiza seguridad.json
# con las novedades de las últimas 24 horas en Colombia.
# ============================================================
on:
  # Cada hora en punto (siempre activo, no solo el día E)
  schedule:
    - cron: '5 * * * *'   # minuto 5 de cada hora (UTC)

  # Disparo manual
  workflow_dispatch:

jobs:
  scrape-noticias:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Ejecutar scraper de noticias
        id: scrape
        run: |
          mkdir -p logs
          python3 scripts/scrape_noticias.py 2>&1 | tee logs/last_news_run.log
        continue-on-error: true

      - name: Detectar cambios
        id: cambios
        run: |
          if git diff --quiet seguridad.json; then
            echo "hay_cambios=false" >> $GITHUB_OUTPUT
            echo "✓ Sin cambios en seguridad.json"
          else
            echo "hay_cambios=true" >> $GITHUB_OUTPUT
            echo "✓ Cambios detectados en seguridad.json"
          fi

      - name: Commit y push
        if: steps.cambios.outputs.hay_cambios == 'true'
        run: |
          git config user.name "News Bot"
          git config user.email "newsbot@meli-dashboard.local"
          git add seguridad.json logs/
          git commit -m "📰 Noticias actualizadas $(date -u +'%Y-%m-%d %H:%M UTC')"
          git push

      - name: Subir log
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: news-scrape-log-${{ github.run_id }}
          path: logs/last_news_run.log
          retention-days: 3
