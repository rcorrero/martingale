document.addEventListener('DOMContentLoaded', () => {
    const socket = io();

    const assetsTableBody = document.querySelector('#assets-table tbody');
    const assetInput = document.getElementById('asset-input');
    const assetSuggestions = document.getElementById('asset-suggestions');
    const assetSearchInput = document.getElementById('asset-search');
    const cashBalance = document.getElementById('cash-balance');
    const holdingsList = document.getElementById('holdings-list');
    const tradeForm = document.getElementById('trade-form');
    const quantityInput = document.getElementById('quantity-input');
    const tradeMessage = document.getElementById('trade-message');
    const sellAllBtn = document.getElementById('sell-all-btn');
    const chartsContainer = document.getElementById('charts-container');
    const transactionsTableBody = document.querySelector('#transactions-table tbody');
    const timeAndSalesFeed = document.getElementById('time-and-sales-feed');
    
    // Time display elements
    const utcTimeEl = document.getElementById('utc-time');
    const localTimeEl = document.getElementById('local-time');
    
    // Performance elements
    const portfolioValueEl = document.getElementById('portfolio-value');
    const totalPnlEl = document.getElementById('total-pnl');
    const totalReturnEl = document.getElementById('total-return');
    const realizedPnlEl = document.getElementById('realized-pnl');
    const unrealizedPnlEl = document.getElementById('unrealized-pnl');
    const availableCashEl = document.getElementById('available-cash');
    
    const charts = {};
    let userTransactions = [];
    let userPortfolio = {};
    let portfolioPieChart = null;
    let previousPrices = {}; // Track previous prices for color comparison
    let openInterestData = {}; // Store open interest data for all assets
    let currentlyHighlightedSymbol = null; // Track currently highlighted holding

    // Function to apply asset search filter
    function applyAssetSearchFilter() {
        if (!assetSearchInput) return;
        
        const searchTerm = assetSearchInput.value.toLowerCase().trim();
        if (!searchTerm) return; // No filter to apply
        
        const rows = assetsTableBody.querySelectorAll('tr');
        rows.forEach(row => {
            const symbolCell = row.querySelector('td');
            if (symbolCell) {
                const symbolText = symbolCell.textContent.toLowerCase();
                if (symbolText.includes(searchTerm)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            }
        });
    }

    // Define colors for each instrument
    const instrumentColors = {
        'XQR': '#f7931a', // Orange
        'ZLN': '#627eea', // Blue  
        'FWX': '#2ca02c', // Green
        'KVT': '#d62728', // Red
        'PGH': '#9467bd', // Purple
        'MWZ': '#8c564b', // Brown
        'DQB': '#e377c2', // Pink
        'LNC': '#17becf', // Cyan
        'EPS': '#ff7f0e', // Bright Orange
        'ACT': '#1f77b4', // Steel Blue
        'ORD': '#bcbd22'  // Olive
    };

    function getInstrumentColor(symbol) {
        return instrumentColors[symbol] || '#6c757d'; // Default gray for unknown instruments
    }

    // Time display functions
    function updateTimeDisplay() {
        const now = new Date();
        
        // Format UTC time
        const utcTimeString = now.toUTCString().substring(17, 25); // Extract HH:MM:SS
        utcTimeEl.textContent = utcTimeString;
        
        // Format local time in user's timezone
        const localTimeString = now.toLocaleTimeString('en-US', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        localTimeEl.textContent = localTimeString;
    }
    
    function initializeTimeDisplay() {
        // Update time immediately
        updateTimeDisplay();
        
        // Update time every second
        setInterval(updateTimeDisplay, 1000);
    }

    function calculateVWAP(symbol) {
        if (!userPortfolio.position_info || !userPortfolio.position_info[symbol]) {
            return null;
        }
        const posInfo = userPortfolio.position_info[symbol];
        if (posInfo.total_quantity > 0 && posInfo.total_cost > 0) {
            return posInfo.total_cost / posInfo.total_quantity;
        }
        return null;
    }

    const createOrUpdatePortfoliePieChart = function() {
        const canvas = document.getElementById('portfolio-pie-chart');
        if (!canvas) return;

        // Calculate portfolio values for the pie chart
        const portfolioData = [];
        const portfolioLabels = [];
        const portfolioColors = [];
        let totalValue = 0;

        // Add cash if available
        if (userPortfolio.cash && userPortfolio.cash > 0) {
            portfolioData.push(userPortfolio.cash);
            portfolioLabels.push('Cash');
            portfolioColors.push('#94a3b8'); // Gray for cash
            totalValue += userPortfolio.cash;
        }

        // Add holdings if available
        if (userPortfolio.holdings) {
            // We need to get current asset prices to calculate portfolio values
            fetch('/api/assets')
                .then(response => response.json())
                .then(assets => {
                    // Clear previous data
                    portfolioData.length = 0;
                    portfolioLabels.length = 0;
                    portfolioColors.length = 0;
                    totalValue = 0;

                    // Add cash
                    if (userPortfolio.cash && userPortfolio.cash > 0) {
                        portfolioData.push(userPortfolio.cash);
                        portfolioLabels.push('Cash');
                        portfolioColors.push('#94a3b8');
                        totalValue += userPortfolio.cash;
                    }

                    // Add holdings
                    for (const symbol in userPortfolio.holdings) {
                        const quantity = userPortfolio.holdings[symbol];
                        if (quantity > 0 && assets[symbol]) {
                            const value = quantity * assets[symbol].price;
                            portfolioData.push(value);
                            portfolioLabels.push(symbol);
                            portfolioColors.push(getInstrumentColor(symbol));
                            totalValue += value;
                        }
                    }

                    // Only show chart if there's data
                    if (portfolioData.length === 0) {
                        // Hide chart if no data
                        canvas.style.display = 'none';
                        return;
                    } else {
                        canvas.style.display = 'block';
                    }

                    if (!portfolioPieChart) {
                        // Create new chart
                        const ctx = canvas.getContext('2d');
                        portfolioPieChart = new Chart(ctx, {
                            type: 'doughnut',
                            data: {
                                labels: portfolioLabels,
                                datasets: [{
                                    data: portfolioData,
                                    backgroundColor: portfolioColors,
                                    borderColor: '#2d3748',
                                    borderWidth: 2,
                                    hoverBorderWidth: 4,
                                    hoverBorderColor: '#00ff88',
                                    hoverOffset: 0
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: true,
                                cutout: '50%',
                                layout: {
                                    padding: 10
                                },
                                plugins: {
                                    legend: {
                                        display: false
                                    },
                                    tooltip: {
                                        enabled: true,
                                        mode: 'nearest',
                                        intersect: true,
                                        backgroundColor: 'rgba(10, 14, 26, 0.95)',
                                        titleColor: '#00ff88',
                                        bodyColor: '#e2e8f0',
                                        borderColor: '#2d3748',
                                        borderWidth: 1,
                                        cornerRadius: 6,
                                        displayColors: false,
                                        titleFont: {
                                            family: 'JetBrains Mono, Consolas, Monaco, monospace',
                                            size: 12,
                                            weight: 600
                                        },
                                        bodyFont: {
                                            family: 'JetBrains Mono, Consolas, Monaco, monospace',
                                            size: 11
                                        },
                                        padding: 10,
                                        caretSize: 6,
                                        callbacks: {
                                            title: function() {
                                                return ''; // No title
                                            },
                                            label: function(context) {
                                                const value = context.parsed;
                                                const ticker = context.label;
                                                
                                                // Calculate total from the dataset
                                                const total = context.dataset.data.reduce((sum, val) => sum + val, 0);
                                                const percentage = formatNumber(((value / total) * 100), 1);
                                                
                                                return [
                                                    `${ticker}: ${percentage}%`,
                                                    `Value: ${formatCurrencyLocale(value)}`
                                                ];
                                            }
                                        }
                                    }
                                },
                                interaction: {
                                    mode: 'nearest',
                                    intersect: true
                                },
                                onHover: (event, activeElements) => {
                                    event.native.target.style.cursor = activeElements.length > 0 ? 'pointer' : 'default';
                                    
                                    // Cross-highlighting: highlight corresponding holdings list item
                                    if (activeElements.length > 0) {
                                        const activeElement = activeElements[0];
                                        const label = portfolioPieChart.data.labels[activeElement.index];
                                        
                                        // Only update if the highlighted symbol changed
                                        if (currentlyHighlightedSymbol !== label) {
                                            currentlyHighlightedSymbol = label;
                                            clearHoldingsHighlight();
                                            highlightHoldingsItem(label);
                                        }
                                    } else {
                                        // Only clear if something was highlighted
                                        if (currentlyHighlightedSymbol !== null) {
                                            currentlyHighlightedSymbol = null;
                                            clearHoldingsHighlight();
                                        }
                                    }
                                },
                                elements: {
                                    arc: {
                                        borderWidth: 2
                                    }
                                },
                                animation: {
                                    animateRotate: true,
                                    duration: 1000
                                }
                            }
                        });
                    } else {
                        // Update existing chart
                        portfolioPieChart.data.labels = portfolioLabels;
                        portfolioPieChart.data.datasets[0].data = portfolioData;
                        portfolioPieChart.data.datasets[0].backgroundColor = portfolioColors;
                        portfolioPieChart.data.datasets[0].hoverOffset = 0;
                        portfolioPieChart.update();
                    }
                    
                    // Update holdings list with cross-highlighting capabilities
                    updateHoldingsCrossHighlighting();
                })
                .catch(error => {
                    console.error('Error fetching assets for pie chart:', error);
                });
        }
    };

    // Cross-highlighting helper functions
    function highlightHoldingsItem(symbol) {
        clearHoldingsHighlight();
        const holdingsItems = document.querySelectorAll('#holdings-list li');
        holdingsItems.forEach(item => {
            const symbolBadge = item.querySelector('.symbol-badge');
            if (symbolBadge) {
                const badgeText = symbolBadge.textContent;
                // Check for exact match or Cash/CASH equivalence
                if (badgeText === symbol || 
                    (symbol === 'Cash' && badgeText === 'CASH') ||
                    (symbol === 'CASH' && badgeText === 'Cash')) {
                    item.style.backgroundColor = 'rgba(0, 255, 136, 0.2)';
                    item.style.borderColor = '#00ff88';
                    item.style.boxShadow = '0 0 10px rgba(0, 255, 136, 0.3)';
                    item.style.transform = 'scale(1.02)';
                    item.style.transition = 'all 0.2s ease';
                }
            }
        });
    }

    function clearHoldingsHighlight() {
        const holdingsItems = document.querySelectorAll('#holdings-list li');
        holdingsItems.forEach(item => {
            item.style.backgroundColor = '';
            item.style.borderColor = '';
            item.style.boxShadow = '';
            item.style.transform = '';
        });
    }

    function highlightPieChartSegment(symbol) {
        if (!portfolioPieChart) return;
        
        const chartData = portfolioPieChart.data;
        const segmentIndex = chartData.labels.indexOf(symbol);
        
        if (segmentIndex !== -1) {
            // Temporarily set active elements to highlight the segment
            portfolioPieChart.setActiveElements([{
                datasetIndex: 0,
                index: segmentIndex
            }]);
            portfolioPieChart.update('none');
        }
    }

    function clearPieChartHighlight() {
        if (!portfolioPieChart) return;
        
        portfolioPieChart.setActiveElements([]);
        portfolioPieChart.update('none');
    }

    function updateHoldingsCrossHighlighting() {
        const holdingsItems = document.querySelectorAll('#holdings-list li');
        holdingsItems.forEach(item => {
            // Remove any existing event listeners
            item.onmouseenter = null;
            item.onmouseleave = null;
            
            const symbolBadge = item.querySelector('.symbol-badge');
            if (symbolBadge) {
                let symbol = symbolBadge.textContent;
                // Map CASH to 'Cash' for pie chart consistency
                if (symbol === 'CASH') {
                    symbol = 'Cash';
                }
                
                item.onmouseenter = () => {
                    highlightPieChartSegment(symbol);
                    item.style.backgroundColor = 'rgba(0, 255, 136, 0.1)';
                    item.style.borderColor = '#00ff88';
                    item.style.transform = 'scale(1.02)';
                    item.style.transition = 'all 0.2s ease';
                };
                
                item.onmouseleave = () => {
                    clearPieChartHighlight();
                    item.style.backgroundColor = '';
                    item.style.borderColor = '';
                    item.style.transform = '';
                };
                
                // Add cursor pointer
                item.style.cursor = 'pointer';
            }
        });
    }

    // Time and Sales functionality
    const maxTimeAndSalesEntries = 50; // Keep only the most recent 50 entries
    
    function addTimeAndSalesEntry(trade, isInitialLoad = false) {
        if (!timeAndSalesFeed) return;
        
        // Use the same date formatting as transaction history
        const formattedTime = formatDateTime(trade.timestamp);
        
        const row = document.createElement('tr');
        row.className = trade.type; // 'buy' or 'sell' for styling
        
        // Get instrument color for symbol badge
        const color = getInstrumentColor(trade.symbol);
        
        row.innerHTML = `
            <td style="color: #94a3b8; font-size: 11px;">${formattedTime}</td>
            <td><span class="symbol-badge" style="background-color: ${color};">${trade.symbol}</span></td>
            <td style="color: ${trade.type === 'buy' ? '#7dda58' : '#f85149'}; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">
                ${trade.type}
            </td>
            <td style="color: #e2e8f0; font-family: 'JetBrains Mono', monospace;">${formatQuantity(trade.quantity)}</td>
            <td style="color: #00d4ff; font-family: 'JetBrains Mono', monospace;">${formatCurrencyLocale(trade.price)}</td>
        `;
        
        // Always add to the top (most recent first) since backend data is already sorted newest first
        timeAndSalesFeed.insertBefore(row, timeAndSalesFeed.firstChild);
        
        // Remove old entries if we exceed the maximum
        while (timeAndSalesFeed.children.length > maxTimeAndSalesEntries) {
            timeAndSalesFeed.removeChild(timeAndSalesFeed.lastChild);
        }
        
        // Scroll to top to show the new entry (scroll the container, not the tbody)
        if (!isInitialLoad) {
            const container = document.getElementById('time-and-sales-container');
            if (container) {
                container.scrollTop = 0;
            }
        }
    }

    // Enhanced number formatting functions with locale support
    function formatNumber(number, decimals = 2) {
        return new Intl.NumberFormat(undefined, {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        }).format(number);
    }

    function formatCurrencyLocale(amount) {
        return new Intl.NumberFormat(undefined, {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(amount);
    }

    function formatQuantity(quantity) {
        return formatNumber(quantity, 0);
    }

    function formatPercentage(value) {
        return new Intl.NumberFormat(undefined, {
            style: 'percent',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(value / 100);
    }

    function formatDateTime(timestamp) {
        const date = new Date(timestamp);
        
        // Format date and time using user's local timezone and locale
        const dateString = date.toLocaleDateString(undefined, {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        });
        
        const timeString = date.toLocaleTimeString(undefined, {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        
        return `${dateString} ${timeString}`;
    }

    function updateTransactionsTable() {
        if (!transactionsTableBody) return;
        
        transactionsTableBody.innerHTML = '';
        // Show most recent transactions first
        const sortedTransactions = [...userTransactions].reverse();
        
        sortedTransactions.forEach(transaction => {
            const color = getInstrumentColor(transaction.symbol);
            const row = document.createElement('tr');
            row.className = `transaction-${transaction.type}`;
            row.innerHTML = `
                <td style="color: #94a3b8; font-size: 11px;">${formatDateTime(transaction.timestamp)}</td>
                <td><span class="symbol-badge" style="background-color: ${color};">${transaction.symbol}</span></td>
                <td style="color: ${transaction.type === 'buy' ? '#7dda58' : '#f85149'}; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">
                    ${transaction.type}
                </td>
                <td style="color: #e2e8f0; font-family: 'JetBrains Mono', monospace;">${formatQuantity(transaction.quantity)}</td>
                <td style="color: #00d4ff; font-family: 'JetBrains Mono', monospace;">${formatCurrencyLocale(transaction.price)}</td>
                <td style="color: #e2e8f0; font-family: 'JetBrains Mono', monospace; font-weight: 600;">${formatCurrencyLocale(transaction.total_cost)}</td>
            `;
            transactionsTableBody.appendChild(row);
        });
    }

    function updatePerformance() {
        fetch('/api/performance')
            .then(response => response.json())
            .then(performance => {
                // Update portfolio value
                portfolioValueEl.textContent = formatCurrencyLocale(performance.portfolio_value);
                
                // Update total P&L with color coding
                totalPnlEl.textContent = formatCurrencyLocale(performance.total_pnl);
                totalPnlEl.className = 'performance-value ' + (performance.total_pnl >= 0 ? 'positive' : 'negative');
                
                // Update total return with color coding
                totalReturnEl.textContent = formatPercentage(performance.total_return);
                totalReturnEl.className = 'performance-value ' + (performance.total_return >= 0 ? 'positive' : 'negative');
                
                // Update realized P&L with color coding
                realizedPnlEl.textContent = formatCurrencyLocale(performance.realized_pnl);
                realizedPnlEl.className = 'performance-value ' + (performance.realized_pnl >= 0 ? 'positive' : 'negative');
                
                // Update unrealized P&L with color coding
                unrealizedPnlEl.textContent = formatCurrencyLocale(performance.unrealized_pnl);
                unrealizedPnlEl.className = 'performance-value ' + (performance.unrealized_pnl >= 0 ? 'positive' : 'negative');
                
                // Get cash from portfolio API since it's not in performance response
                fetch('/api/portfolio')
                    .then(response => response.json())
                    .then(portfolio => {
                        availableCashEl.textContent = formatCurrencyLocale(portfolio.cash);
                    })
                    .catch(error => {
                        console.error('Error fetching portfolio for cash:', error);
                    });
            })
            .catch(error => {
                console.error('Error fetching performance data:', error);
                // Set fallback values to prevent NaN display
                portfolioValueEl.textContent = formatCurrencyLocale(100000);
                totalPnlEl.textContent = formatCurrencyLocale(0);
                totalReturnEl.textContent = formatPercentage(0);
                realizedPnlEl.textContent = formatCurrencyLocale(0);
                unrealizedPnlEl.textContent = formatCurrencyLocale(0);
                availableCashEl.textContent = formatCurrencyLocale(100000);
            });
    }

    // Dynamic Chart Management System
    let chartInstances = []; // Array of chart objects
    let chartCount = 2; // Default number of charts
    let availableAssets = []; // Store available assets for autocomplete

    function initializeChartSystem() {
        // Load available assets for autocomplete
        fetch('/api/assets')
            .then(response => response.json())
            .then(assets => {
                availableAssets = Object.keys(assets).sort(); // Sort alphabetically
                createInitialCharts();
            });
    }

    function createInitialCharts() {
        // Create initial charts with first available assets
        updateChartLayout();
        
        // Auto-populate charts with first available assets
        setTimeout(() => {
            const assetsToLoad = availableAssets.slice(0, chartCount);
            assetsToLoad.forEach((symbol, index) => {
                if (chartInstances[index]) {
                    addSymbolToChart(index, symbol);
                }
            });
        }, 100); // Small delay to ensure charts are created
    }

    function updateChartLayout() {
        // Clear existing charts
        chartsContainer.innerHTML = '';
        chartInstances = [];

        // Update grid layout based on chart count
        if (chartCount === 1) {
            chartsContainer.style.gridTemplateColumns = '1fr';
        } else if (chartCount === 2) {
            chartsContainer.style.gridTemplateColumns = '1fr 1fr';
        } else if (chartCount === 3) {
            chartsContainer.style.gridTemplateColumns = 'repeat(3, 1fr)';
        } else if (chartCount === 4) {
            chartsContainer.style.gridTemplateColumns = 'repeat(2, 1fr)';
        }

        // Create new chart containers
        for (let i = 0; i < chartCount; i++) {
            createChartContainer(i);
        }
    }

    function createChartContainer(index) {
        const chartContainer = document.createElement('div');
        chartContainer.className = 'chart-container';
        chartContainer.dataset.chartIndex = index;

        // Chart controls
        const controlsDiv = document.createElement('div');
        controlsDiv.className = 'chart-controls-header';
        controlsDiv.innerHTML = `
            <div class="chart-symbol-controls">
                <input type="text" 
                       placeholder="Enter symbol" 
                       class="chart-symbol-input" 
                       list="chart-assets-${index}"
                       data-chart-index="${index}">
                <datalist id="chart-assets-${index}">
                    ${availableAssets.map(symbol => `<option value="${symbol}">`).join('')}
                </datalist>
                <button class="add-symbol-btn" data-chart-index="${index}">Add</button>
                <button class="clear-chart-btn" data-chart-index="${index}">Clear</button>
            </div>
            <div class="chart-symbols-list" id="chart-symbols-${index}">
                <!-- Active symbols will be listed here -->
            </div>
        `;

        // Canvas for the chart
        const canvas = document.createElement('canvas');
        canvas.id = `chart-canvas-${index}`;

        chartContainer.appendChild(controlsDiv);
        chartContainer.appendChild(canvas);
        chartsContainer.appendChild(chartContainer);

        // Initialize empty chart
        const ctx = canvas.getContext('2d');
        const chartInstance = {
            index: index,
            chart: new Chart(ctx, {
                type: 'line',
                data: {
                    datasets: []
                },
                options: getChartOptions()
            }),
            symbols: [] // Track which symbols are on this chart
        };

        chartInstances.push(chartInstance);

        // Add event listeners
        setupChartEventListeners(index);
    }

    function getChartOptions() {
        return {
            responsive: true,
            maintainAspectRatio: false,
            backgroundColor: '#1a1f2e',
            layout: {
                padding: {
                    top: 15,
                    right: 20,
                    bottom: 15,  // Reduced from 60 to 15 to eliminate empty space
                    left: 20
                }
            },
            parsing: {
                xAxisKey: 'x',
                yAxisKey: 'y'
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'minute',
                        displayFormats: {
                            minute: 'HH:mm'
                        },
                        tooltipFormat: 'MMM dd, HH:mm:ss'
                    },
                    adapters: {
                        date: {} // Use default date adapter
                    },
                    ticks: {
                        maxRotation: 0,
                        maxTicksLimit: 5,
                        font: {
                            family: 'JetBrains Mono, Consolas, Monaco, monospace',
                            size: 12  // Increased font size for better visibility
                        },
                        color: '#94a3b8',
                        padding: 5,  // Reduced from 15 to 5 for less spacing
                        autoSkip: true,
                        autoSkipPadding: 10  // Reduced from 25 to 10
                    },
                    grid: {
                        color: 'rgba(45, 55, 72, 0.8)',
                        borderColor: '#2d3748'
                    },
                    border: {
                        color: '#2d3748'
                    }
                },
                y: {
                    beginAtZero: false,
                    grid: {
                        color: 'rgba(45, 55, 72, 0.6)',
                        borderColor: '#2d3748'
                    },
                    border: {
                        color: '#2d3748'
                    },
                    ticks: {
                        font: {
                            family: 'JetBrains Mono, Consolas, Monaco, monospace',
                            size: 10
                        },
                        color: '#94a3b8',
                        callback: function(value) {
                            return formatCurrencyLocale(value);
                        }
                    }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#e2e8f0',
                        font: {
                            family: 'JetBrains Mono, Consolas, Monaco, monospace',
                            size: 11
                        },
                        usePointStyle: true,
                        padding: 15
                    }
                },
                tooltip: {
                    enabled: true,
                    mode: 'nearest',
                    intersect: false,
                    backgroundColor: 'rgba(10, 14, 26, 0.95)',
                    titleColor: '#00ff88',
                    bodyColor: '#e2e8f0',
                    borderColor: '#2d3748',
                    borderWidth: 1,
                    cornerRadius: 6,
                    titleFont: {
                        family: 'JetBrains Mono, Consolas, Monaco, monospace',
                        size: 12,
                        weight: 600
                    },
                    bodyFont: {
                        family: 'JetBrains Mono, Consolas, Monaco, monospace',
                        size: 11
                    },
                    padding: 10
                }
            },
            elements: {
                line: {
                    borderWidth: 2
                },
                point: {
                    radius: 0,
                    hoverRadius: 6,
                    hitRadius: 10
                }
            },
            interaction: {
                intersect: false,
                mode: 'nearest'
            }
        };
    }

    function setupChartEventListeners(chartIndex) {
        // Add symbol button
        const addBtn = document.querySelector(`[data-chart-index="${chartIndex}"].add-symbol-btn`);
        const clearBtn = document.querySelector(`[data-chart-index="${chartIndex}"].clear-chart-btn`);
        const symbolInput = document.querySelector(`[data-chart-index="${chartIndex}"].chart-symbol-input`);

        addBtn.addEventListener('click', () => {
            const symbol = symbolInput.value.toUpperCase().trim();
            if (symbol && availableAssets.includes(symbol)) {
                addSymbolToChart(chartIndex, symbol);
                symbolInput.value = '';
            }
        });

        clearBtn.addEventListener('click', () => {
            clearChart(chartIndex);
        });

        symbolInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                addBtn.click();
            }
        });

        // Auto-uppercase input
        symbolInput.addEventListener('input', (e) => {
            e.target.value = e.target.value.toUpperCase();
        });
    }

    function addSymbolToChart(chartIndex, symbol) {
        const chartInstance = chartInstances[chartIndex];
        if (!chartInstance) return;

        // Check if symbol already exists on this chart
        if (chartInstance.symbols.includes(symbol)) {
            return; // Already exists
        }

        // Add symbol to chart
        chartInstance.symbols.push(symbol);

        // Get asset history and add to chart
        fetch('/api/assets/history')
            .then(response => response.json())
            .then(historyData => {
                const history = historyData[symbol] || [];
                
                // Filter out invalid data points and sort by timestamp
                const validHistory = history
                    .filter(point => point.time && point.price && 
                           typeof point.time === 'number' && 
                           typeof point.price === 'number' &&
                           !isNaN(point.time) && !isNaN(point.price))
                    .sort((a, b) => a.time - b.time)
                    .map(point => ({x: point.time, y: point.price})); // Transform to Chart.js format
                
                const color = getInstrumentColor(symbol);
                
                const dataset = {
                    label: symbol,
                    data: validHistory,
                    borderColor: color,
                    backgroundColor: color + '20', // Add transparency
                    tension: 0, // No curve - straight lines between points
                    pointRadius: 0,
                    pointHoverRadius: 6,
                    pointHoverBackgroundColor: color,
                    pointHoverBorderColor: '#0a0e1a',
                    pointHoverBorderWidth: 2,
                    stepped: false, // Ensure smooth line connections, not stepped
                    spanGaps: false // Don't connect across missing data points
                };

                chartInstance.chart.data.datasets.push(dataset);
                chartInstance.chart.update('none'); // Update without animation for faster display
                
                // Force a redraw to ensure proper line rendering
                setTimeout(() => {
                    chartInstance.chart.update();
                }, 10);

                // Update symbols list display
                updateSymbolsList(chartIndex);
            });
    }

    function removeSymbolFromChart(chartIndex, symbol) {
        const chartInstance = chartInstances[chartIndex];
        if (!chartInstance) return;

        // Remove from symbols array
        const symbolIndex = chartInstance.symbols.indexOf(symbol);
        if (symbolIndex > -1) {
            chartInstance.symbols.splice(symbolIndex, 1);
        }

        // Remove dataset from chart
        const datasetIndex = chartInstance.chart.data.datasets.findIndex(dataset => dataset.label === symbol);
        if (datasetIndex > -1) {
            chartInstance.chart.data.datasets.splice(datasetIndex, 1);
            chartInstance.chart.update();
        }

        // Update symbols list display
        updateSymbolsList(chartIndex);
    }

    function clearChart(chartIndex) {
        const chartInstance = chartInstances[chartIndex];
        if (!chartInstance) return;

        chartInstance.symbols = [];
        chartInstance.chart.data.datasets = [];
        chartInstance.chart.update();
        updateSymbolsList(chartIndex);
    }

    function updateSymbolsList(chartIndex) {
        const symbolsList = document.getElementById(`chart-symbols-${chartIndex}`);
        const chartInstance = chartInstances[chartIndex];
        
        if (!symbolsList || !chartInstance) return;

        symbolsList.innerHTML = chartInstance.symbols.map(symbol => {
            const color = getInstrumentColor(symbol);
            return `
                <span class="chart-symbol-tag" style="background-color: ${color}20; border-left: 3px solid ${color};">
                    ${symbol}
                    <button class="remove-symbol-btn" onclick="removeSymbolFromChart(${chartIndex}, '${symbol}')">&times;</button>
                </span>
            `;
        }).join('');
    }

    function updateChartData(symbol, newDataPoint) {
        // Update all charts that contain this symbol
        chartInstances.forEach(chartInstance => {
            if (chartInstance.symbols.includes(symbol)) {
                const dataset = chartInstance.chart.data.datasets.find(ds => ds.label === symbol);
                if (dataset) {
                    // Check if we already have a data point at this exact timestamp
                    const existingPoint = dataset.data.find(point => point.x === newDataPoint.x);
                    if (existingPoint) {
                        // Update existing point instead of adding duplicate
                        existingPoint.y = newDataPoint.y;
                    } else {
                        // Add new data point
                        dataset.data.push(newDataPoint);
                        // Keep only last 100 points
                        if (dataset.data.length > 100) {
                            dataset.data.shift();
                        }
                    }
                    chartInstance.chart.update('none');
                }
            }
        });
    }

    // Initialize chart system on page load
    // Note: This will be called from the main DOMContentLoaded listener

    // Global function for removing symbols (called from onclick)
    window.removeSymbolFromChart = removeSymbolFromChart;

    // Function to handle symbol badge clicks - puts symbol in trade input
    function handleSymbolBadgeClick(symbol) {
        const assetInput = document.getElementById('asset-input');
        if (assetInput) {
            assetInput.value = symbol.toUpperCase();
        }
    }

    // Function to add click handlers to all symbol badges
    function addSymbolBadgeClickHandlers() {
        // Add event delegation for dynamically created symbol badges
        document.addEventListener('click', function(e) {
            if (e.target.classList.contains('symbol-badge')) {
                const symbol = e.target.textContent.trim();
                handleSymbolBadgeClick(symbol);
            }
        });
    }    function updateVWAPLine(symbol) {
        if (!charts[symbol]) return;
        
        const chart = charts[symbol];
        const vwap = calculateVWAP(symbol);
        
        // Only show VWAP line if user currently holds a position
        if (vwap && userPortfolio.holdings && userPortfolio.holdings[symbol] > 0) {
            chart.options.plugins.annotation.annotations.vwapLine = {
                type: 'line',
                yMin: vwap,
                yMax: vwap,
                borderColor: '#00d4ff', // Terminal cyan
                borderWidth: 2,
                borderDash: [8, 4],
                label: {
                    content: `VWAP: ${formatCurrencyLocale(vwap)}`,
                    enabled: true,
                    position: 'end',
                    backgroundColor: 'rgba(0, 212, 255, 0.8)',
                    color: '#0a0e1a',
                    font: {
                        family: 'JetBrains Mono, Consolas, Monaco, monospace',
                        size: 10,
                        weight: 600
                    },
                    padding: 4,
                    borderRadius: 4
                }
            };
        } else {
            // Remove VWAP line if no current position
            delete chart.options.plugins.annotation.annotations.vwapLine;
        }
        chart.update();
    }

    function updatePriceDisplay(symbol) {
        const priceDisplayEl = document.getElementById(`price-display-${symbol}`);
        if (!priceDisplayEl) return;
        
        // Get current price from assets data (we'll need to fetch this)
        fetch('/api/assets')
            .then(response => response.json())
            .then(assets => {
                const currentPrice = assets[symbol].price;
                let html = `<div class="current-price">Last Price: ${formatCurrencyLocale(currentPrice)}</div>`;
                
                // Add VWAP if user has position
                if (userPortfolio && userPortfolio.holdings && userPortfolio.holdings[symbol] > 0) {
                    const vwap = calculateVWAP(symbol);
                    if (vwap) {
                        html += `<div class="vwap-price">VWAP: ${formatCurrencyLocale(vwap)}</div>`;
                    }
                }
                
                priceDisplayEl.innerHTML = html;
            });
    }

    // Initial load of transaction history, portfolio, and global transactions
    Promise.all([
        fetch('/api/transactions').then(response => response.json()),
        fetch('/api/portfolio').then(response => response.json()),
        fetch('/api/global-transactions').then(response => response.json())
    ]).then(([transactions, portfolio, globalTransactions]) => {
        userTransactions = transactions;
        userPortfolio = portfolio;
        updateTransactionsTable();
        updatePortfolio();
        updatePerformance();
        
        // Load initial global transactions into Time & Sales (already sorted newest first from backend)
        globalTransactions.forEach(transaction => {
            addTimeAndSalesEntry(transaction, true); // Pass flag for initial loading
        });
        
        // Update VWAP lines for all charts after portfolio is loaded
        Object.keys(charts).forEach(symbol => {
            updateVWAPLine(symbol);
        });
    });

    // Note: Charts are now dynamically created by user interaction
    // No automatic chart creation on page load

    // Handle real-time performance updates
    socket.on('performance_update', () => {
        updatePerformance();
    });

    // Update performance on price changes (for unrealized P&L)
    socket.on('price_update', (assets) => {
        updateAssetsTable(assets);
        
        // Update performance as prices change to reflect current unrealized P&L
        updatePerformance();
        
        // Update pie chart with new portfolio values
        createOrUpdatePortfoliePieChart();
    });

    function updateAssetsTable(assets) {
        // Fetch current open interest data
        fetch('/api/open-interest')
            .then(response => response.json())
            .then(openInterest => {
                openInterestData = openInterest;
                
                assetsTableBody.innerHTML = '';
                // Sort symbols alphabetically
                const sortedSymbols = Object.keys(assets).sort();
                for (const symbol of sortedSymbols) {
                    const currentPrice = assets[symbol].price;
                    const color = getInstrumentColor(symbol);
                    
                    // Determine price color based on change
                    let priceColor = '#e2e8f0'; // Default neutral color (terminal text)
                    if (previousPrices[symbol] !== undefined) {
                        if (currentPrice > previousPrices[symbol]) {
                            priceColor = '#7dda58'; // Bright green for price increase
                        } else if (currentPrice < previousPrices[symbol]) {
                            priceColor = '#f85149'; // Bright red for price decrease
                        }
                        // If prices are equal, keep neutral color
                    }
                    
                    // Store current price for next comparison
                    previousPrices[symbol] = currentPrice;
                    
                    // Get open interest for this symbol
                    const totalOpenInterest = openInterest[symbol] || 0;
                    
                    const row = `<tr style="border-left: 4px solid ${color};">
                        <td><span class="symbol-badge" style="background-color: ${color};">${symbol}</span></td>
                        <td style="color: ${priceColor}; font-weight: 600; font-family: 'JetBrains Mono', monospace;">${formatCurrencyLocale(currentPrice)}</td>
                        <td style="color: #94a3b8; font-family: 'JetBrains Mono', monospace;">${formatQuantity(totalOpenInterest)}</td>
                    </tr>`;
                    assetsTableBody.innerHTML += row;
                    
                    // Update price display for each chart
                    updatePriceDisplay(symbol);
                }
                
                // Reapply search filter after table update
                applyAssetSearchFilter();
            })
            .catch(error => {
                console.error('Error fetching open interest:', error);
                
                // Fallback to showing just prices without open interest
                assetsTableBody.innerHTML = '';
                // Sort symbols alphabetically
                const sortedSymbols = Object.keys(assets).sort();
                for (const symbol of sortedSymbols) {
                    const currentPrice = assets[symbol].price;
                    const color = getInstrumentColor(symbol);
                    
                    let priceColor = '#e2e8f0';
                    if (previousPrices[symbol] !== undefined) {
                        if (currentPrice > previousPrices[symbol]) {
                            priceColor = '#7dda58';
                        } else if (currentPrice < previousPrices[symbol]) {
                            priceColor = '#f85149';
                        }
                    }
                    
                    previousPrices[symbol] = currentPrice;
                    
                    const row = `<tr style="border-left: 4px solid ${color};">
                        <td><span class="symbol-badge" style="background-color: ${color};">${symbol}</span></td>
                        <td style="color: ${priceColor}; font-weight: 600; font-family: 'JetBrains Mono', monospace;">${formatCurrencyLocale(currentPrice)}</td>
                        <td style="color: #94a3b8; font-family: 'JetBrains Mono', monospace;">${formatQuantity(0)}</td>
                    </tr>`;
                    assetsTableBody.innerHTML += row;
                    
                    updatePriceDisplay(symbol);
                }
                
                // Reapply search filter after table update
                applyAssetSearchFilter();
            });
    }

    // Update charts with new price data
    socket.on('price_chart_update', (data) => {
        const { symbol, time, price } = data;
        updateChartData(symbol, {x: time, y: price});
    });

    // Initial load of assets for trade form
    fetch('/api/assets')
        .then(response => response.json())
        .then(assets => {
            assetSuggestions.innerHTML = '';
            // Sort symbols alphabetically
            const sortedSymbols = Object.keys(assets).sort();
            for (const symbol of sortedSymbols) {
                const option = document.createElement('option');
                option.value = symbol;
                assetSuggestions.appendChild(option);
            }
        });

    // Update portfolio display
    function updatePortfolio() {
        fetch('/api/portfolio')
            .then(response => response.json())
            .then(portfolio => {
                userPortfolio = portfolio;
                cashBalance.textContent = formatNumber(portfolio.cash, 2);
                
                // Fetch current prices to calculate market values
                fetch('/api/assets')
                    .then(response => response.json())
                    .then(assets => {
                        holdingsList.innerHTML = '';
                        
                        // Add cash as the first item in holdings list
                        const cashColor = '#00d4ff'; // Cash color for consistency
                        const cashItem = `<li style="border-left: 3px solid ${cashColor}; padding-left: 12px; background: rgba(0, 0, 0, 0.3);">
                            <span class="symbol-badge" style="background-color: ${cashColor}; margin-right: 8px;">CASH</span>
                            <span style="color: #e2e8f0; font-family: 'JetBrains Mono', monospace; font-weight: 600;">$${formatNumber(portfolio.cash, 2)}</span>
                        </li>`;
                        holdingsList.innerHTML += cashItem;
                        
                        // Add asset holdings
                        for (const symbol in portfolio.holdings) {
                            const quantity = portfolio.holdings[symbol];
                            if (quantity > 0) {
                                const color = getInstrumentColor(symbol);
                                const vwap = calculateVWAP(symbol);
                                
                                // Calculate market value using current price from assets or previousPrices
                                const currentPrice = assets[symbol]?.price || previousPrices[symbol];
                                const marketValue = currentPrice ? quantity * currentPrice : null;
                                
                                // Build the holding display with clear labels
                                const quantityDisplay = `<span style="color: #94a3b8; font-size: 11px;">QTY:</span> <span style="color: #e2e8f0; font-family: 'JetBrains Mono', monospace; font-weight: 600;">${formatQuantity(quantity)}</span>`;
                                const marketValueDisplay = marketValue ? ` <span style="color: #94a3b8; font-size: 11px; margin-left: 12px;">VALUE:</span> <span style="color: #7dda58; font-family: 'JetBrains Mono', monospace; font-weight: 600;">${formatCurrencyLocale(marketValue)}</span>` : '';
                                const vwapDisplay = vwap ? ` <span style="color: #94a3b8; font-size: 11px; margin-left: 12px;">VWAP:</span> <span style="color: #00d4ff; font-family: 'JetBrains Mono', monospace; font-weight: 600;">${formatCurrencyLocale(vwap)}</span>` : '';
                                
                                const item = `<li style="border-left: 3px solid ${color}; padding-left: 12px; background: rgba(0, 0, 0, 0.3);">
                                    <div style="display: flex; align-items: center; flex-wrap: wrap;">
                                        <span class="symbol-badge" style="background-color: ${color}; margin-right: 12px;">${symbol}</span>
                                        ${quantityDisplay}${marketValueDisplay}${vwapDisplay}
                                    </div>
                                </li>`;
                                holdingsList.innerHTML += item;
                            }
                        }
                        
                        // Update pie chart
                        createOrUpdatePortfoliePieChart();
                        
                        // Set up cross-highlighting after holdings list is updated
                        setTimeout(() => {
                            updateHoldingsCrossHighlighting();
                        }, 100); // Small delay to ensure DOM is updated
                    })
                    .catch(error => {
                        console.error('Error fetching assets for portfolio:', error);
                    });
            });
    }

    socket.on('portfolio_update', (portfolio) => {
        userPortfolio = portfolio;
        updatePortfolio();
        updatePerformance();
        
        // Update VWAP lines for all charts when portfolio changes
        Object.keys(charts).forEach(symbol => {
            updateVWAPLine(symbol);
        });
        
        // Update pie chart
        createOrUpdatePortfoliePieChart();
        
        // Update assets table with new open interest data
        fetch('/api/assets')
            .then(response => response.json())
            .then(assets => {
                updateAssetsTable(assets);
            });
    });

    // Handle new transactions
    socket.on('transaction_added', (transaction) => {
        userTransactions.push(transaction);
        updateTransactionsTable();
        
        // Update VWAP line for this specific instrument
        updateVWAPLine(transaction.symbol);
    });

    // Handle Global Transaction updates for Time & Sales
    socket.on('global_transaction_update', (transaction) => {
        addTimeAndSalesEntry(transaction);
    });

    // Handle Time and Sales updates (keep for backward compatibility)
    socket.on('time_and_sales_update', (trade) => {
        addTimeAndSalesEntry(trade);
    });

    // Handle real-time performance updates
    socket.on('performance_update', () => {
        updatePerformance();
    });

    // Auto-populate quantity based on asset selection and position
    assetInput.addEventListener('input', () => {
        const symbol = assetInput.value.toUpperCase();
        assetInput.value = symbol; // Force uppercase
        
        if (userPortfolio && userPortfolio.holdings && userPortfolio.holdings[symbol] > 0) {
            quantityInput.value = userPortfolio.holdings[symbol];
        } else {
            quantityInput.value = '1';
        }
    });

    // Handle sell all positions button
    sellAllBtn.addEventListener('click', async () => {
        if (!userPortfolio || !userPortfolio.holdings) return;
        
        const positions = Object.entries(userPortfolio.holdings).filter(([symbol, quantity]) => quantity > 0);
        
        if (positions.length === 0) {
            tradeMessage.textContent = 'No positions to sell';
            tradeMessage.style.color = '#fbbf24'; // Terminal warning yellow
            tradeMessage.style.background = 'rgba(251, 191, 36, 0.1)';
            tradeMessage.style.border = '1px solid rgba(251, 191, 36, 0.3)';
            setTimeout(() => {
                tradeMessage.textContent = '';
                tradeMessage.style.background = '';
                tradeMessage.style.border = '';
            }, 3000);
            return;
        }
        
        // Confirm sell all
        if (confirm(`Are you sure you want to sell all ${positions.length} positions?`)) {
            // Disable the button to prevent double-clicking
            sellAllBtn.disabled = true;
            sellAllBtn.style.opacity = '0.6';
            sellAllBtn.style.cursor = 'not-allowed';
            
            let successCount = 0;
            let failCount = 0;
            
            tradeMessage.textContent = `Selling ${positions.length} positions... (0/${positions.length})`;
            tradeMessage.style.color = '#00d4ff'; // Terminal cyan
            tradeMessage.style.background = 'rgba(0, 212, 255, 0.1)';
            tradeMessage.style.border = '1px solid rgba(0, 212, 255, 0.3)';
            
            // Process sells sequentially with a small delay between each
            for (let i = 0; i < positions.length; i++) {
                const [symbol, quantity] = positions[i];
                
                try {
                    // Wait for the previous trade to be acknowledged before sending the next
                    await new Promise((resolve) => {
                        const tradePromise = new Promise((tradeResolve) => {
                            // Set up one-time listener for trade confirmation
                            const handleTradeConfirmation = (data) => {
                                if (data.symbol === symbol) {
                                    socket.off('trade_confirmation', handleTradeConfirmation);
                                    if (data.success) {
                                        successCount++;
                                    } else {
                                        failCount++;
                                    }
                                    tradeResolve();
                                }
                            };
                            socket.on('trade_confirmation', handleTradeConfirmation);
                            
                            // Send the trade
                            socket.emit('trade', {
                                symbol: symbol,
                                type: 'sell',
                                quantity: quantity
                            });
                        });
                        
                        // Add timeout to prevent hanging
                        const timeout = setTimeout(() => {
                            failCount++;
                            resolve();
                        }, 5000);
                        
                        tradePromise.then(() => {
                            clearTimeout(timeout);
                            // Update progress message
                            const completed = successCount + failCount;
                            tradeMessage.textContent = `Selling ${positions.length} positions... (${completed}/${positions.length})`;
                            resolve();
                        });
                    });
                    
                    // Small delay between trades to prevent overwhelming the server
                    if (i < positions.length - 1) {
                        await new Promise(resolve => setTimeout(resolve, 200));
                    }
                } catch (error) {
                    console.error(`Error selling ${symbol}:`, error);
                    failCount++;
                }
            }
            
            // Re-enable the button
            sellAllBtn.disabled = false;
            sellAllBtn.style.opacity = '1';
            sellAllBtn.style.cursor = 'pointer';
            
            // Show final result
            if (failCount === 0) {
                tradeMessage.textContent = `Successfully sold all ${successCount} positions!`;
                tradeMessage.style.color = '#7dda58'; // High contrast green
                tradeMessage.style.background = 'rgba(0, 255, 136, 0.1)';
                tradeMessage.style.border = '1px solid rgba(0, 255, 136, 0.3)';
            } else {
                tradeMessage.textContent = `Sold ${successCount}/${positions.length} positions (${failCount} failed)`;
                tradeMessage.style.color = '#fbbf24'; // Terminal warning yellow
                tradeMessage.style.background = 'rgba(251, 191, 36, 0.1)';
                tradeMessage.style.border = '1px solid rgba(251, 191, 36, 0.3)';
            }
            
            setTimeout(() => {
                tradeMessage.textContent = '';
                tradeMessage.style.background = '';
                tradeMessage.style.border = '';
            }, 5000);
        }
    });

    // Handle trade form submission
    tradeForm.addEventListener('submit', (event) => {
        event.preventDefault();
        const tradeType = event.submitter.value;
        const symbol = assetInput.value.toUpperCase().trim();
        const quantity = quantityInput.value;

        if (!symbol) {
            tradeMessage.textContent = 'Please enter a symbol';
            tradeMessage.style.color = '#f85149'; // High contrast red
            tradeMessage.style.background = 'rgba(248, 81, 73, 0.1)';
            tradeMessage.style.border = '1px solid rgba(248, 81, 73, 0.3)';
            setTimeout(() => {
                tradeMessage.textContent = '';
                tradeMessage.style.background = '';
                tradeMessage.style.border = '';
            }, 3000);
            return;
        }

        if (quantity > 0) {
            socket.emit('trade', {
                symbol: symbol,
                type: tradeType,
                quantity: quantity
            });
            quantityInput.value = '';
            assetInput.value = '';
        }
    });

    // Display trade confirmation messages
    socket.on('trade_confirmation', (data) => {
        tradeMessage.textContent = data.message;
        if (data.success) {
            tradeMessage.style.color = '#7dda58'; // High contrast green
            tradeMessage.style.background = 'rgba(125, 218, 88, 0.1)';
            tradeMessage.style.border = '1px solid rgba(125, 218, 88, 0.3)';
        } else {
            tradeMessage.style.color = '#f85149'; // High contrast red
            tradeMessage.style.background = 'rgba(248, 81, 73, 0.1)';
            tradeMessage.style.border = '1px solid rgba(248, 81, 73, 0.3)';
        }
        setTimeout(() => {
            tradeMessage.textContent = '';
            tradeMessage.style.background = '';
            tradeMessage.style.border = '';
        }, 3000);
    });

    // Initialize time display
    initializeTimeDisplay();
    
    // Initial portfolio load
    updatePortfolio();

    // Asset search functionality
    if (assetSearchInput) {
        assetSearchInput.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase().trim();
            const rows = assetsTableBody.querySelectorAll('tr');
            
            rows.forEach(row => {
                const symbolCell = row.querySelector('td');
                if (symbolCell) {
                    const symbolText = symbolCell.textContent.toLowerCase();
                    if (symbolText.includes(searchTerm)) {
                        row.style.display = '';
                    } else {
                        row.style.display = 'none';
                    }
                }
            });
        });
    }

    // Initialize chart controls
    const chartCountSelect = document.getElementById('chart-count');
    if (chartCountSelect) {
        chartCountSelect.addEventListener('change', (e) => {
            chartCount = parseInt(e.target.value);
            updateChartLayout();
        });
    }

    const addChartBtn = document.getElementById('add-chart-btn');
    if (addChartBtn) {
        addChartBtn.addEventListener('click', () => {
            if (chartCount < 4) {
                chartCount++;
                chartCountSelect.value = chartCount;
                updateChartLayout();
            }
        });
    }

    const clearAllBtn = document.getElementById('clear-all-charts-btn');
    if (clearAllBtn) {
        clearAllBtn.addEventListener('click', () => {
            chartInstances.forEach((_, index) => clearChart(index));
        });
    }

    // Initialize chart system
    initializeChartSystem();
    
    // Set up symbol badge click handlers
    addSymbolBadgeClickHandlers();
});
