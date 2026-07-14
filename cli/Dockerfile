FROM python:3.13-slim

WORKDIR /workspace

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY web/ web/
COPY setup.py .

RUN pip install -e .

ENTRYPOINT ["python", "-m", "src.cli"]