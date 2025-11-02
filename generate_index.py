"""
Generate dynamic index.html for GitHub Pages based on actual output files.
"""
from pathlib import Path
import json
from datetime import datetime

def scan_outputs(outputs_dir: Path) -> dict:
    """Scan outputs directory and return structure of generated files."""
    structure = {}
    
    if not outputs_dir.exists():
        return structure
    
    # Scan all topic folders
    for topic_dir in outputs_dir.iterdir():
        if not topic_dir.is_dir():
            continue
        
        topic_name = topic_dir.name
        structure[topic_name] = {}
        
        # Scan all source folders within topic
        for source_dir in topic_dir.iterdir():
            if not source_dir.is_dir():
                continue
            
            source_name = source_dir.name
            files: dict[str, str | None] = {
                'html': None,
                'csv': None,
                'png': None
            }
            
            # Find files
            for file in source_dir.iterdir():
                if file.suffix == '.html':
                    files['html'] = f"outputs/{topic_name}/{source_name}/{file.name}"
                elif file.suffix == '.csv':
                    files['csv'] = f"outputs/{topic_name}/{source_name}/{file.name}"
                elif file.suffix == '.png':
                    files['png'] = f"outputs/{topic_name}/{source_name}/{file.name}"
            
            structure[topic_name][source_name] = files
    
    return structure

def format_topic_name(topic: str) -> str:
    """Format topic name for display."""
    return topic.replace('_', ' ').title()

def generate_html(structure: dict, output_file: Path):
    """Generate HTML index page."""
    
    html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HypePlot Showcase - Multi-Source Academic Keyword Tracking</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <header>
        <div class="container">
            <h1>📊 HypePlot</h1>
            <p class="tagline">Multi-Source Academic Keyword Tracking</p>
            <p class="subtitle">Track trends across 11 data sources with configurable time buckets</p>
        </div>
    </header>

    <main class="container">
        <section class="intro">
            <h2>About This Project</h2>
            <p>
                HypePlot is a comprehensive tool for tracking keyword trends across multiple platforms and timeframes. 
                It combines <strong>12 powerful data sources</strong> to give you a complete picture of topic evolution:
            </p>
            <div class="sources-grid">
                <div class="source-tag">🐙 GitHub</div>
                <div class="source-tag">📚 arXiv</div>
                <div class="source-tag">💬 Reddit</div>
                <div class="source-tag">▶️ YouTube</div>
                <div class="source-tag">🎓 Scholar</div>
                <div class="source-tag">📈 Trends</div>
                <div class="source-tag">📰 News</div>
                <div class="source-tag">🐦 Twitter</div>
                <div class="source-tag">⚖️ Patents</div>
                <div class="source-tag">📦 Packages</div>
                <div class="source-tag">💼 Jobs</div>
                <div class="source-tag">💰 Grants</div>
            </div>
            <p style="margin-top: 20px;">
                <strong>Flexible Time Bucketing:</strong> Analyze data at yearly, monthly, quarterly, or custom intervals (e.g., every 10 days).
            </p>
        </section>

        <section class="showcase">
            <h2>📚 Showcase Examples</h2>
'''
    
    # Generate showcase cards for each topic
    for topic, sources in sorted(structure.items()):
        topic_display = format_topic_name(topic)
        
        html += f'''
            <div class="showcase-card">
                <h3>{topic_display}</h3>
                <p class="chart-description">
                    Data from {', '.join(sources.keys())} sources
                </p>
                <div class="button-group">
'''
        
        # Add buttons for each source
        for source, files in sorted(sources.items()):
            if files['html']:
                html += f'                    <a href="{files["html"]}" class="button primary">{source.title()} Chart</a>\n'
            elif files['csv']:
                # Has CSV but no HTML - show info message
                html += f'                    <span class="button disabled" title="Visualization not generated">{source.title()} (CSV only)</span>\n'
        
        # Add CSV download links
        has_csv = any(files['csv'] for files in sources.values())
        if has_csv:
            html += '                    <br>\n'
            for source, files in sorted(sources.items()):
                if files['csv']:
                    html += f'                    <a href="{files["csv"]}" class="button secondary" download>{source.title()} CSV</a>\n'
        
        html += '''                </div>
            </div>
'''
    
    html += '''
        </section>

        <section class="usage">
            <h2>🚀 Use It Yourself</h2>
            <p>Want to analyze your own topics? Install and run HypePlot locally:</p>
            
            <div class="code-block">
                <code># Clone the repository
git clone https://github.com/quotentiroler/HypePlot
cd HypePlot

# Install dependencies (requires Python 3.12+ and uv)
pip install uv
uv sync

# Run with different sources and time buckets
uv run hype "FHIR" 2024 2025 plot --source github --bucket monthly
uv run hype "python" 2023 2025 plot --source github,arxiv --bucket quarterly
uv run hype "covid" 2020 2024 plot --source patents,news --bucket yearly

# Custom buckets (10-day periods)
uv run hype "AI" 2025 2025 plot --source github --bucket days:10</code>
            </div>

            <h3>Available Sources</h3>
            <ul>
                <li><code>github</code> - Repository counts and metrics</li>
                <li><code>arxiv</code> - Research preprints</li>
                <li><code>reddit</code> - Discussion posts via Pushshift</li>
                <li><code>youtube</code> - Video content</li>
                <li><code>scholar</code> - Academic publications</li>
                <li><code>trends</code> - Google search interest</li>
                <li><code>news</code> - News articles (NewsAPI)</li>
                <li><code>twitter</code> - Mentions (requires API access)</li>
                <li><code>patents</code> - USPTO patents</li>
                <li><code>packages</code> - PyPI download stats</li>
                <li><code>jobs</code> - Job postings (Adzuna)</li>
                <li><code>grants</code> - NSF research grants and funding</li>
            </ul>

            <h3>Time Bucket Options</h3>
            <ul>
                <li><code>--bucket yearly</code> - Annual aggregation (1 year)</li>
                <li><code>--bucket quarterly</code> - Quarterly periods (3 months)</li>
                <li><code>--bucket monthly</code> - Monthly periods</li>
                <li><code>--bucket days:N</code> - Custom N-day periods</li>
            </ul>
        </section>

        <section class="features">
            <h2>✨ Features</h2>
            <div class="feature-grid">
                <div class="feature">
                    <h3>🔍 12 Data Sources</h3>
                    <p>Comprehensive coverage across platforms</p>
                </div>
                <div class="feature">
                    <h3>📅 Flexible Bucketing</h3>
                    <p>Yearly, monthly, quarterly, or custom intervals</p>
                </div>
                <div class="feature">
                    <h3>📈 Interactive Plots</h3>
                    <p>Built with Plotly for rich interactivity</p>
                </div>
                <div class="feature">
                    <h3>💾 CSV Export</h3>
                    <p>All data exported for further analysis</p>
                </div>
                <div class="feature">
                    <h3>🐍 Modern Python</h3>
                    <p>Built with uv, type hints, async-ready</p>
                </div>
                <div class="feature">
                    <h3>🤖 Automation Ready</h3>
                    <p>GitHub Actions for scheduled updates</p>
                </div>
            </div>
        </section>

        <section class="cta">
            <h2>Get Started</h2>
            <div class="button-group">
                <a href="https://github.com/quotentiroler/HypePlot" 
                   class="button primary" target="_blank" rel="noopener">
                    View on GitHub
                </a>
                <a href="https://github.com/quotentiroler/HypePlot/issues" 
                   class="button secondary" target="_blank" rel="noopener">
                    Report Issues
                </a>
            </div>
        </section>
    </main>

    <footer>
        <div class="container">
            <p>
                Built with Python • uv • Plotly • 12 Data Sources
            </p>
            <p class="update-info">
                Last updated: <span id="last-update">Check GitHub Actions</span>
            </p>
        </div>
    </footer>

    <script>
        // Try to load last update time
        fetch('last-update.txt')
            .then(response => response.text())
            .then(data => {
                document.getElementById('last-update').textContent = data.trim();
            })
            .catch(() => {
                document.getElementById('last-update').textContent = 'See GitHub Actions for build status';
            });
    </script>
</body>
</html>'''
    
    output_file.write_text(html, encoding='utf-8')
    print(f"✅ Generated {output_file}")

if __name__ == "__main__":
    outputs_dir = Path("outputs")
    structure = scan_outputs(outputs_dir)
    
    print(f"Found {len(structure)} topics:")
    for topic, sources in structure.items():
        print(f"  - {topic}: {', '.join(sources.keys())}")
    
    generate_html(structure, Path("index.html"))
