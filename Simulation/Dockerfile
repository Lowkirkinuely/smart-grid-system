FROM python:3.11-slim

RUN python -m pip install --upgrade pip

WORKDIR /simulator

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Simulation/ ./Simulation

ENV BACKEND_URL=http://backend:8000

CMD ["python", "Simulation/simulator.py", "--mode", "escalate"]
