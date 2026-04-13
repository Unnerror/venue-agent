FROM public.ecr.aws/lambda/python:3.11

COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir

COPY app/ ./app/
COPY data/ ./data/

CMD ["app.handler.lambda_handler"]