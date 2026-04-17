FROM public.ecr.aws/lambda/python:3.11

# Install gcc for packages that need compilation
RUN yum install -y gcc && yum clean all

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir

# Copy application code
COPY app/ ./app/
COPY data/ ./data/

# Create EFS mount point directory
# (actual mounting is configured in AWS Lambda settings, not here)
RUN mkdir -p /mnt/efs

# Default handler: chat Lambda
# Override with app.scraper_handler.lambda_handler for scraper Lambda
CMD ["app.handler.lambda_handler"]
