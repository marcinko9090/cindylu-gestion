FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py administrar.py cxc_review.py statements.py wa_documents.py ./
COPY templates templates
COPY static static
RUN useradd -m -u 10001 cindy && mkdir /data && chown cindy:cindy /data
USER cindy
ENV CINDY_DATA=/data CINDY_HOST=0.0.0.0 PORT=8765 CINDY_HTTPS=1
EXPOSE 8765
VOLUME ["/data"]
CMD ["python", "app.py", "--no-browser"]
