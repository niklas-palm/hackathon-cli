FROM python:3.9-slim

ENV AWS_DEFAULT_REGION="eu-north-1"

WORKDIR /hackathon-cli

COPY setup.* .
COPY src ./src

RUN ls -l
RUN pip install --no-cache-dir .

CMD ["bash"]