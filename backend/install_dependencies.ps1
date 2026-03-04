# 依赖安装脚本
# 使用系统Python安装必需的依赖

Write-Host "正在安装Flask和其他依赖..." -ForegroundColor Green

# 安装核心依赖
python -m pip install --upgrade pip
python -m pip install flask
python -m pip install requests
python -m pip install paddlepaddle
python -m pip install paddleocr
python -m pip install PyMuPDF
python -m pip install Pillow

Write-Host "依赖安装完成！" -ForegroundColor Green
Write-Host "现在可以运行: python src/app.py" -ForegroundColor Yellow
