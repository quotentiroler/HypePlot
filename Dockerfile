FROM python:3.12

# Install uv for dependency management
RUN pip install uv

WORKDIR /data

# Copy project files
COPY pyproject.toml uv.lock ./
COPY hype.py scholar.py trends.py utils_io.py extract_occurrences.py ./

# Install dependencies
RUN uv sync

# Default command
CMD ["uv", "run", "hype", "plot", "--help"]
