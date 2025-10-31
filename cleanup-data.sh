#!/bin/bash
# Production Data Cleanup Script

echo "Cleaning production data files..."

# Reset data files to empty state
echo '{}' > portfolios.json
echo '[]' > global_transactions.json
echo '[]' > users.json

# Remove development logs if they exist
rm -f martingale.log

echo "Data files reset for production deployment."
echo "Remember to:"
echo "1. Set a secure SECRET_KEY in .env"
echo "2. Ensure HTTPS is configured"
echo "3. Set up proper firewall rules"
echo "4. Configure log rotation"