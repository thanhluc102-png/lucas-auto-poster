# Sử dụng image Python chuẩn
FROM python:3.10-slim

# Cài đặt các thư viện hệ thống cần thiết cho Playwright (Chromium)
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc
WORKDIR /app

# Copy các file code vào container
COPY requirements.txt .

# Cài đặt thư viện Python
RUN pip install --no-cache-dir -r requirements.txt

# Cài đặt trình duyệt ảo Chromium cho Playwright
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy toàn bộ mã nguồn còn lại vào
COPY . .

# Hugging Face yêu cầu chạy Web ở port 7860
ENV PORT=7860
EXPOSE 7860

# Khởi chạy server Flask
CMD ["python", "app.py"]
