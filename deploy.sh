#!/bin/bash
# Production deployment script for Martingale Trading Platform

set -e  # Exit on any error

echo "🚀 Starting Martingale Trading Platform deployment..."

# Check if running as root (not recommended for production)
if [ "$EUID" -eq 0 ]; then
    echo "⚠️  Warning: Running as root is not recommended for production"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install production requirements
echo "📥 Installing production requirements..."
pip install -r requirements-prod.txt

# Check if production environment file exists
if [ ! -f ".env.production" ]; then
    echo "❌ Production environment file (.env.production) not found!"
    echo "Please copy .env.production template and configure it with production values."
    exit 1
fi

# Copy production environment
cp .env.production .env

# Validate SECRET_KEY is set
if grep -q "your-secure-random-secret-key-here" .env; then
    echo "❌ Please set a secure SECRET_KEY in .env.production"
    exit 1
fi

# Create log directory
mkdir -p logs

echo "✅ Deployment preparation complete!"
echo ""
echo "🌐 To start the application:"
echo "   source .venv/bin/activate"
echo "   python start_services.py"
echo ""
echo "📋 Production checklist:"
echo "   □ Set secure SECRET_KEY in .env.production"
echo "   □ Configure reverse proxy (nginx/apache)"
echo "   □ Set up SSL certificates"
echo "   □ Configure firewall rules"
echo "   □ Set up monitoring and log rotation"
echo "   □ Configure backup strategy for data files"