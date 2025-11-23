document.addEventListener('DOMContentLoaded', () => {
    const socket = io();

    const assetsTableBody = document.querySelector('#assets-table tbody');
    const assetInput = document.getElementById('asset-input');
    const assetSuggestions = document.getElementById('asset-suggestions');
    const assetSearchInput = document.getElementById('asset-search');
    const mobileAssetSearchInput = document.getElementById('mobile-asset-search');
    const cashBalance = document.getElementById('cash-balance');
    const holdingsList = document.getElementById('holdings-list');
    const tradeForm = document.getElementById('trade-form');
    const quantityInput = document.getElementById('quantity-input');
    const tradeMessage = document.getElementById('trade-message');
    const sellAllBtn = document.getElementById('sell-all-btn');
    const buyingPowerCashEl = document.getElementById('buying-power-cash');
    const buyingPowerPriceEl = document.getElementById('buying-power-price');
    const buyingPowerSharesEl = document.getElementById('buying-power-shares');
    const chartsContainer = document.getElementById('charts-container');
    const transactionsTableBody = document.querySelector('#transactions-table tbody');
    const allTransactionsTableBody = document.querySelector('#all-transactions-table tbody');
    const leaderboardTableBody = document.querySelector('#leaderboard-table tbody');
    const portfolioValueLatestEl = document.getElementById('portfolio-value-latest');
    
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
    const rootStyles = getComputedStyle(document.documentElement);
    const themeAccentColor = rootStyles.getPropertyValue('--terminal-border-strong').trim() || '#3b82f6';
    const themeGlowColor = rootStyles.getPropertyValue('--terminal-glow').trim() || 'rgba(59, 130, 246, 0.28)';
    let userTransactions = [];
    let globalTransactions = [];
    let userPortfolio = {};
    let currentUserId = null; // Store current user ID for filtering
    let portfolioPieChart = null;
    let mobilePortfolioPieChart = null;
    let previousPrices = {}; // Track previous prices for color comparison
    let openInterestData = {}; // Store open interest data for all assets
    let currentlyHighlightedSymbol = null; // Track currently highlighted holding
    let activeHoldingSymbol = null; // Track the holding currently hovered by the user
    let latestAssetPrices = {}; // Cache latest prices for buying power calculations
    let availableCashAmount = 0; // Track current available cash
    const GLOBAL_TRANSACTIONS_LIMIT = 100;
    const PORTFOLIO_HISTORY_LIMIT = 300;
    let portfolioValueChart = null;
    let mobilePortfolioChart = null;
    let portfolioHistoryData = [];
    let portfolioHistoryRefreshTimer = null;
    let portfolioHistoryRequest = null;
    let latestAssetsSnapshot = null;

    const EXPIRING_NOTIFICATION_THRESHOLD = 120; // 2 minutes
    const EXPIRING_COUNTDOWN_THRESHOLD = 60;      // 1 minute
    const EXPIRING_SNOOZE_MS = 60000;             // 1 minute snooze after manual dismissal

    const expiringAssetNotifications = new Map();
    const expiringNotificationSnoozed = new Map();
    const notificationAutoCloseTimers = new Map();

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
    // Dynamic color assignment for instruments
    const instrumentColors = {};
    
    // Predefined color palette for random assignment (fallback only)
    const colorPalette = [
        '#f7931a', '#627eea', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#17becf', '#ff7f0e', '#1f77b4',
        '#bcbd22', '#ff6384', '#36a2eb', '#ffce56', '#4bc0c0',
        '#ff9f40', '#9966ff', '#c9cbcf', '#00d084', '#fe6b8b'
    ];
    
    let colorIndex = 0;

    function hexToRgba(hex, alpha = 0.3) {
        if (typeof hex !== 'string') {
            return `rgba(59, 130, 246, ${alpha})`;
        }

        let normalized = hex.trim();
        if (normalized.startsWith('#')) {
            normalized = normalized.slice(1);
        }

        if (normalized.length === 3) {
            normalized = normalized.split('').map(ch => ch + ch).join('');
        }

        const intVal = parseInt(normalized, 16);
        if (Number.isNaN(intVal)) {
            return `rgba(59, 130, 246, ${alpha})`;
        }

        const r = (intVal >> 16) & 255;
        const g = (intVal >> 8) & 255;
        const b = intVal & 255;

        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }

    function getInstrumentColor(symbol, assetData = null) {
        const directColor = typeof assetData === 'string'
            ? assetData
            : (assetData && assetData.color) ? assetData.color : null;

        // If a definitive color is provided, cache and return it immediately
        if (directColor) {
            instrumentColors[symbol] = directColor;
            return directColor;
        }

        // If color already cached, return it
        if (instrumentColors[symbol]) {
            return instrumentColors[symbol];
        }

        // Fallback: assign a new color from the palette
        const color = colorPalette[colorIndex % colorPalette.length];
        instrumentColors[symbol] = color;
        colorIndex++;

        return color;
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

    // Clear mobile asset search on load/restore to avoid preserved user text
    function clearMobileAssetSearch() {
        if (!mobileAssetSearchInput) return;
        try {
            mobileAssetSearchInput.value = '';
            // turn off autocomplete to reduce browser autofill restoring
            mobileAssetSearchInput.setAttribute('autocomplete', 'off');
        } catch (err) {
            // ignore
        }
    }

    // Clear on initial load
    clearMobileAssetSearch();

    // Some browsers restore pages from bfcache — clear when pageshow indicates a persisted page
    window.addEventListener('pageshow', (e) => {
        if (e.persisted) {
            clearMobileAssetSearch();
        }
    });

    // Also try to clear before unload to avoid saving state in some browsers
    window.addEventListener('beforeunload', () => {
        if (mobileAssetSearchInput) mobileAssetSearchInput.value = '';
    });
    
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
        const mobileCanvas = document.getElementById('mobile-portfolio-pie-chart');
        
        if (!canvas && !mobileCanvas) return;

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
                        // Hide charts if no data
                        if (canvas) canvas.style.display = 'none';
                        if (mobileCanvas) mobileCanvas.style.display = 'none';
                        return;
                    } else {
                        if (canvas) canvas.style.display = 'block';
                        if (mobileCanvas) mobileCanvas.style.display = 'block';
                    }

                    // Chart configuration object
                    const chartConfig = {
                        type: 'doughnut',
                        data: {
                            labels: portfolioLabels,
                            datasets: [{
                                data: portfolioData,
                                backgroundColor: portfolioColors,
                                borderColor: '#2d3748',
                                borderWidth: 2,
                                hoverBorderWidth: 4,
                                hoverBorderColor: themeAccentColor,
                                hoverBackgroundColor: themeAccentColor,
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
                                    titleColor: themeAccentColor,
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
                                    const label = event.chart.data.labels[activeElement.index];
                                    
                                    // Only update if the highlighted symbol changed
                                    if (currentlyHighlightedSymbol !== label) {
                                        currentlyHighlightedSymbol = label;
                                        clearHoldingsHighlight(true);
                                        highlightHoldingsItem(label);
                                    }
                                } else {
                                    // Only clear if something was highlighted
                                    clearAllCrossHighlights();
                                }
                            },
                            onLeave: () => {
                                clearAllCrossHighlights();
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
                    };

                    // Create or update desktop chart
                    if (canvas) {
                        if (!portfolioPieChart) {
                            const ctx = canvas.getContext('2d');
                            portfolioPieChart = new Chart(ctx, chartConfig);
                        } else {
                            clearAllCrossHighlights();
                            portfolioPieChart.data.labels = portfolioLabels;
                            portfolioPieChart.data.datasets[0].data = portfolioData;
                            portfolioPieChart.data.datasets[0].backgroundColor = portfolioColors;
                            portfolioPieChart.data.datasets[0].hoverOffset = 0;
                            portfolioPieChart.update();
                        }
                        
                        // Ensure chart hover state clears when pointer leaves canvas
                        if (!canvas.dataset.hoverExitBound) {
                            const handleChartHoverExit = () => {
                                clearAllCrossHighlights();
                            };

                            canvas.addEventListener('mouseleave', handleChartHoverExit);
                            canvas.addEventListener('pointerleave', handleChartHoverExit);
                            canvas.addEventListener('mouseout', handleChartHoverExit);
                            canvas.addEventListener('touchend', handleChartHoverExit);
                            canvas.addEventListener('touchcancel', handleChartHoverExit);
                            canvas.dataset.hoverExitBound = 'true';
                        }
                    }
                    
                    // Create or update mobile chart
                    if (mobileCanvas) {
                        if (!mobilePortfolioPieChart) {
                            const ctx = mobileCanvas.getContext('2d');
                            mobilePortfolioPieChart = new Chart(ctx, chartConfig);
                        } else {
                            mobilePortfolioPieChart.data.labels = portfolioLabels;
                            mobilePortfolioPieChart.data.datasets[0].data = portfolioData;
                            mobilePortfolioPieChart.data.datasets[0].backgroundColor = portfolioColors;
                            mobilePortfolioPieChart.data.datasets[0].hoverOffset = 0;
                            mobilePortfolioPieChart.update();
                        }
                    }
                    
                    // Update holdings list with cross-highlighting capabilities
                    updateHoldingsCrossHighlighting();
                })
                .catch(error => {
                    // Error fetching assets for pie chart
                    if (latestAssetsSnapshot) {
                        evaluateExpiringHoldings(latestAssetsSnapshot);
                    }
                });
        }
    };

    // Cross-highlighting helper functions
    const HOLDING_HIGHLIGHT_STYLE = {
        background: 'rgba(59, 130, 246, 0.18)',
        border: themeAccentColor,
        boxShadow: `0 0 18px ${themeGlowColor}`,
        transform: 'scale(1.015)'
    };

    function applyHoldingHighlight(item, animate = true) {
        if (!item) return;

        if (!animate) {
            item.classList.add('no-transition');
        }

        item.style.backgroundColor = HOLDING_HIGHLIGHT_STYLE.background;
        item.style.borderColor = HOLDING_HIGHLIGHT_STYLE.border;
        item.style.boxShadow = HOLDING_HIGHLIGHT_STYLE.boxShadow;
        item.style.transform = HOLDING_HIGHLIGHT_STYLE.transform;

        if (!animate) {
            requestAnimationFrame(() => item.classList.remove('no-transition'));
        }
    }

    function resetHoldingHighlight(item) {
        if (!item) return;
        item.classList.remove('no-transition');
        item.style.backgroundColor = '';
        item.style.borderColor = '';
        item.style.boxShadow = '';
        item.style.transform = '';
    }

    function highlightHoldingsItem(symbol) {
        clearHoldingsHighlight(true);
        const holdingsItems = document.querySelectorAll('#holdings-list li');
        holdingsItems.forEach(item => {
            const itemSymbol = item.dataset.symbol || item.querySelector('.symbol-badge')?.textContent;
            if (!itemSymbol) {
                return;
            }

            // Check for exact match or Cash/CASH equivalence
            if (itemSymbol === symbol ||
                (symbol === 'Cash' && itemSymbol === 'CASH') ||
                (symbol === 'CASH' && itemSymbol === 'Cash')) {
                applyHoldingHighlight(item, false);
            }
        });
    }

    function clearHoldingsHighlight(force = false) {
        const holdingsItems = document.querySelectorAll('#holdings-list li');
        const hoveredItem = document.querySelector('#holdings-list li:hover');

        if (!hoveredItem) {
            activeHoldingSymbol = null;
        }

        holdingsItems.forEach(item => {
            const itemSymbol = (item.dataset.symbol || item.querySelector('.symbol-badge')?.textContent || '').trim();
            if (!force && (item.matches(':hover') ||
                (hoveredItem && activeHoldingSymbol && itemSymbol === activeHoldingSymbol) ||
                (currentlyHighlightedSymbol && itemSymbol === currentlyHighlightedSymbol))) {
                return;
            }
            resetHoldingHighlight(item);
        });

        if (force && hoveredItem) {
            applyHoldingHighlight(hoveredItem, false);
        }
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
        currentlyHighlightedSymbol = null;
    }

    function clearAllCrossHighlights() {
        clearPieChartHighlight();
        clearHoldingsHighlight(true);
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
                    activeHoldingSymbol = symbol;
                    highlightPieChartSegment(symbol);
                    applyHoldingHighlight(item);
                };
                
                item.onmouseleave = () => {
                    if (activeHoldingSymbol === symbol) {
                        activeHoldingSymbol = null;
                    }
                    clearPieChartHighlight();
                    resetHoldingHighlight(item);
                };
                
                // Add cursor pointer
                item.style.cursor = 'pointer';

                // If the pointer is already over this item, immediately apply the hover styling
                const isHovered = item.matches(':hover');

                if (isHovered) {
                    activeHoldingSymbol = symbol;
                    highlightPieChartSegment(symbol);
                    applyHoldingHighlight(item, false);
                } else if (currentlyHighlightedSymbol && currentlyHighlightedSymbol === symbol) {
                    applyHoldingHighlight(item, false);
                } else {
                    if (activeHoldingSymbol === symbol) {
                        activeHoldingSymbol = null;
                    }
                    resetHoldingHighlight(item);
                }
            }
        });
    }

    function setAvailableCash(amount) {
        const numericAmount = Number(amount);
        availableCashAmount = Number.isFinite(numericAmount) ? numericAmount : 0;

        if (availableCashEl) {
            availableCashEl.textContent = formatCurrencyLocale(availableCashAmount);
        }

        updateBuyingPowerDisplay();
    }

    function updateBuyingPowerDisplay() {
        if (buyingPowerCashEl) {
            buyingPowerCashEl.textContent = formatCurrencyLocale(availableCashAmount);
            buyingPowerCashEl.classList.toggle('metric-value-empty', availableCashAmount <= 0);
        }

        if (!buyingPowerPriceEl || !buyingPowerSharesEl) {
            return;
        }

        const symbol = assetInput ? assetInput.value.trim().toUpperCase() : '';
        const rawPrice = symbol ? latestAssetPrices[symbol] : undefined;

        if (!symbol || rawPrice == null) {
            buyingPowerPriceEl.textContent = '--';
            buyingPowerSharesEl.textContent = '--';
            buyingPowerPriceEl.classList.add('metric-value-empty');
            buyingPowerSharesEl.classList.add('metric-value-empty');
            return;
        }

        const numericPrice = Number(rawPrice);
        if (!Number.isFinite(numericPrice) || numericPrice <= 0) {
            buyingPowerPriceEl.textContent = '--';
            buyingPowerSharesEl.textContent = '--';
            buyingPowerPriceEl.classList.add('metric-value-empty');
            buyingPowerSharesEl.classList.add('metric-value-empty');
            return;
        }

        buyingPowerPriceEl.textContent = formatCurrencyLocale(numericPrice);
        buyingPowerPriceEl.classList.remove('metric-value-empty');

        const maxShares = Math.floor(availableCashAmount / numericPrice);
        const clampedShares = Math.max(maxShares, 0);
        buyingPowerSharesEl.textContent = formatNumber(clampedShares, 0);
        buyingPowerSharesEl.classList.toggle('metric-value-empty', clampedShares < 1);
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

    function formatTimeOnly(timestamp) {
        // Compact format for tables - shows only time (HH:MM:SS)
        const date = new Date(timestamp);
        
        const timeString = date.toLocaleTimeString(undefined, {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        
        return timeString;
    }

    function formatCompactDateTime(timestamp) {
        // Compact format - shows MM/DD HH:MM:SS
        const date = new Date(timestamp);
        
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        const seconds = String(date.getSeconds()).padStart(2, '0');
        
        return `${month}/${day} ${hours}:${minutes}:${seconds}`;
    }

    function formatUserIdentifier(userId) {
        if (userId === null || userId === undefined || userId === '') {
            return '--';
        }
        return String(userId);
    }

    function normalizePortfolioHistory(points, limit = PORTFOLIO_HISTORY_LIMIT) {
        if (!Array.isArray(points) || !points.length) {
            return [];
        }

        const sanitized = [];
        for (const raw of points) {
            const rawTime = raw?.time ?? raw?.timestamp ?? raw?.x ?? null;
            const rawValue = raw?.value ?? raw?.portfolio_value ?? raw?.y ?? null;
            const time = Number(rawTime);
            const value = Number(rawValue);

            if (!Number.isFinite(time) || !Number.isFinite(value)) {
                continue;
            }

            sanitized.push({ x: time, y: value });
        }

        if (!sanitized.length) {
            return [];
        }

        sanitized.sort((a, b) => a.x - b.x);

        const deduped = [];
        let lastX = -Infinity;

        for (const point of sanitized) {
            if (point.x === lastX && deduped.length) {
                deduped[deduped.length - 1] = point;
                continue;
            }

            if (point.x < lastX) {
                continue;
            }

            deduped.push(point);
            lastX = point.x;
        }

        if (deduped.length > limit) {
            return deduped.slice(deduped.length - limit);
        }

        return deduped;
    }

    function updatePortfolioHistoryLatestLabel(latestValue = null) {
        if (!portfolioValueLatestEl) {
            return;
        }

        if (latestValue != null) {
            portfolioValueLatestEl.textContent = formatCurrencyLocale(latestValue);
            return;
        }

        if (!portfolioHistoryData.length) {
            portfolioValueLatestEl.textContent = '--';
            return;
        }

        const mostRecent = portfolioHistoryData[portfolioHistoryData.length - 1];
        portfolioValueLatestEl.textContent = formatCurrencyLocale(mostRecent.y);
    }

    function getPortfolioHistoryChartOptions() {
        return {
            responsive: true,
            maintainAspectRatio: false,
            layout: {
                padding: {
                    top: 15,
                    right: 20,
                    bottom: 15,
                    left: 20
                }
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
                        date: {}
                    },
                    ticks: {
                        color: '#94a3b8',
                        maxRotation: 0,
                        maxTicksLimit: 6,
                        font: {
                            family: 'JetBrains Mono, Consolas, Monaco, monospace',
                            size: 12
                        }
                    },
                    grid: {
                        color: 'rgba(45, 55, 72, 0.6)',
                        borderColor: '#2d3748'
                    },
                    border: {
                        color: '#2d3748'
                    }
                },
                y: {
                    beginAtZero: false,
                    ticks: {
                        color: '#94a3b8',
                        callback: (value) => formatCurrencyLocale(value),
                        font: {
                            family: 'JetBrains Mono, Consolas, Monaco, monospace',
                            size: 11
                        }
                    },
                    grid: {
                        color: 'rgba(45, 55, 72, 0.6)',
                        borderColor: '#2d3748'
                    },
                    border: {
                        color: '#2d3748'
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    enabled: true,
                    mode: 'nearest',
                    intersect: false,
                    backgroundColor: 'rgba(10, 14, 26, 0.95)',
                    borderColor: '#2d3748',
                    borderWidth: 1,
                    cornerRadius: 6,
                    titleColor: themeAccentColor,
                    bodyColor: '#e2e8f0',
                    titleFont: {
                        family: 'JetBrains Mono, Consolas, Monaco, monospace',
                        size: 12,
                        weight: 600
                    },
                    bodyFont: {
                        family: 'JetBrains Mono, Consolas, Monaco, monospace',
                        size: 11
                    },
                    callbacks: {
                        label: (context) => formatCurrencyLocale(context.parsed.y)
                    },
                    padding: 10
                }
            },
            elements: {
                line: {
                    borderWidth: 2,
                    tension: 0.25
                },
                point: {
                    radius: 0,
                    hitRadius: 12,
                    hoverRadius: 5
                }
            },
            interaction: {
                mode: 'nearest',
                intersect: false
            }
        };
    }

    function createPortfolioValueChart() {
        if (portfolioValueChart) {
            return portfolioValueChart;
        }

        const canvas = document.getElementById('portfolio-value-chart');
        if (!canvas) {
            return null;
        }

        const ctx = canvas.getContext('2d');
        const accent = themeAccentColor || '#3b82f6';
        const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height || 280);
        gradient.addColorStop(0, `${accent}33`);
        gradient.addColorStop(1, `${accent}00`);

        portfolioValueChart = new Chart(ctx, {
            type: 'line',
            data: {
                datasets: [{
                    label: 'Portfolio Value',
                    data: [],
                    borderColor: accent,
                    backgroundColor: gradient,
                    fill: 'origin',
                    tension: 0.2,
                    cubicInterpolationMode: 'monotone',
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    pointHoverBorderWidth: 2,
                    pointHoverBorderColor: '#0a0e1a',
                    pointHoverBackgroundColor: accent,
                    spanGaps: true,
                    normalized: true
                }]
            },
            options: getPortfolioHistoryChartOptions()
        });

        updatePortfolioHistoryLatestLabel();

        return portfolioValueChart;
    }

    function updatePortfolioValueChart() {
        const chart = createPortfolioValueChart();
        if (!chart) {
            return;
        }

        chart.data.datasets[0].data = portfolioHistoryData.slice();
        chart.update('none');
    }

    function refreshPortfolioHistory(limit = PORTFOLIO_HISTORY_LIMIT) {
        const canvas = document.getElementById('portfolio-value-chart');
        if (!canvas) {
            return Promise.resolve();
        }

        if (portfolioHistoryRequest) {
            return portfolioHistoryRequest;
        }

        portfolioHistoryRequest = fetch(`/api/performance/history?limit=${limit}`)
            .then(response => {
                if (response.status === 401) {
                    window.location.href = '/login';
                    return null;
                }
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (!data || !Array.isArray(data.points)) {
                    return;
                }

                portfolioHistoryData = normalizePortfolioHistory(data.points, limit);

                updatePortfolioValueChart();
                updateMobilePortfolioChart();
                updatePortfolioHistoryLatestLabel();
            })
            .catch(error => {
                console.error('Error fetching portfolio history:', error);
            })
            .finally(() => {
                portfolioHistoryRequest = null;
            });

        return portfolioHistoryRequest;
    }

    function schedulePortfolioHistoryRefresh(delay = 2000) {
        if (portfolioHistoryRefreshTimer) {
            return;
        }

        portfolioHistoryRefreshTimer = setTimeout(() => {
            portfolioHistoryRefreshTimer = null;
            refreshPortfolioHistory();
        }, delay);
    }

    function formatTimeToExpiry(seconds) {
        // Format time remaining until expiration
        if (seconds <= 0) {
            return '<span style="color: #f85149; font-weight: 600;">EXPIRED</span>';
        }
        
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        // Color coding based on urgency (adjusted for shorter asset lifetimes)
        let color = '#94a3b8'; // Default gray
        if (seconds < 60) { // Less than 1 minute
            color = '#f85149'; // Red
        } else if (seconds < 300) { // Less than 5 minutes
            color = '#ff9800'; // Orange
        } else if (seconds < 900) { // Less than 15 minutes
            color = '#ffeb3b'; // Yellow
        }
        
        let formatted = '';
        if (days > 0) {
            formatted = `${days}d ${hours}h`;
        } else if (hours > 0) {
            formatted = `${hours}h ${minutes}m`;
        } else if (minutes > 0) {
            formatted = `${minutes}m`;
        } else {
            // Show seconds countdown when under 1 minute
            formatted = `${secs}s`;
        }
        
        return `<span style="color: ${color}; font-weight: 600; font-family: 'JetBrains Mono', monospace;">${formatted}</span>`;
    }

    function showNotification(message, type = 'info', options = {}) {
        const container = document.getElementById('notification-container');
        if (!container) return null;

        const {
            id = null,
            autoClose = true,
            autoCloseMs = 3000,
            replaceExisting = true,
            onClose = null
        } = options;

        let notification = null;
        if (id) {
            notification = container.querySelector(`.notification[data-notification-id="${id}"]`);
        }

        if (!notification) {
            notification = document.createElement('div');
            if (id) {
                notification.dataset.notificationId = id;
            }
            notification.className = `notification notification-${type}`;

            const messageSpan = document.createElement('span');
            messageSpan.className = 'notification-message';
            messageSpan.innerHTML = message;
            notification.appendChild(messageSpan);

            const closeBtn = document.createElement('button');
            closeBtn.className = 'notification-close';
            closeBtn.textContent = '×';
            closeBtn.onclick = () => {
                removeNotification(notification, id);
                if (typeof onClose === 'function') {
                    onClose();
                }
            };
            notification.appendChild(closeBtn);

            container.appendChild(notification);
        } else if (replaceExisting) {
            notification.className = `notification notification-${type}`;

            let messageSpan = notification.querySelector('.notification-message');
            if (!messageSpan) {
                messageSpan = document.createElement('span');
                messageSpan.className = 'notification-message';
                notification.prepend(messageSpan);
            }
            messageSpan.innerHTML = message;

            let closeBtn = notification.querySelector('.notification-close');
            if (!closeBtn) {
                closeBtn = document.createElement('button');
                closeBtn.className = 'notification-close';
                notification.appendChild(closeBtn);
            }
            closeBtn.textContent = '×';
            closeBtn.onclick = () => {
                removeNotification(notification, id);
                if (typeof onClose === 'function') {
                    onClose();
                }
            };
        }

        if (id) {
            notification.dataset.notificationId = id;
        }

        if (id && notificationAutoCloseTimers.has(id)) {
            clearTimeout(notificationAutoCloseTimers.get(id));
            notificationAutoCloseTimers.delete(id);
        }

        if (autoClose) {
            const timeout = setTimeout(() => {
                removeNotification(notification, id);
                if (typeof onClose === 'function') {
                    onClose();
                }
            }, autoCloseMs);

            if (id) {
                notificationAutoCloseTimers.set(id, timeout);
            }
        }

        return notification;
    }

    function removeNotification(notification, id = null) {
        if (id && notificationAutoCloseTimers.has(id)) {
            clearTimeout(notificationAutoCloseTimers.get(id));
            notificationAutoCloseTimers.delete(id);
        }

        if (notification && notification.parentElement) {
            notification.parentElement.removeChild(notification);
        }
    }

    function removeNotificationById(id) {
        if (!id) return;
        const container = document.getElementById('notification-container');
        if (!container) return;
        const notification = container.querySelector(`.notification[data-notification-id="${id}"]`);
        if (notification) {
            removeNotification(notification, id);
        }
    }

    function formatShortDuration(seconds) {
        const totalSeconds = Math.max(0, Math.floor(seconds));
        const minutes = Math.floor(totalSeconds / 60);
        const secs = totalSeconds % 60;
        if (minutes > 0) {
            return `${minutes}m ${secs.toString().padStart(2, '0')}s`;
        }
        return `${secs}s`;
    }

    function formatCountdownDisplay(seconds) {
        const totalSeconds = Math.max(0, Math.ceil(seconds));
        const minutes = Math.floor(totalSeconds / 60);
        const secs = totalSeconds % 60;
        return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }

    function buildExpiringWarningMessage(symbol, seconds, quantity) {
        return `<strong>${symbol}</strong> expires soon (${formatShortDuration(seconds)}). Holding ${formatQuantity(quantity)} unit(s).`;
    }

    function buildExpiringCountdownMessage(symbol, seconds, quantity) {
        return `<strong>${symbol}</strong> expires in <span class="countdown-timer">${formatCountdownDisplay(seconds)}</span>. Holding ${formatQuantity(quantity)} unit(s).`;
    }

    function startCountdownForEntry(symbol, entry) {
        if (entry.timerId) {
            clearInterval(entry.timerId);
        }

        const tick = () => {
            const remaining = Math.ceil((entry.expiryTimestamp - Date.now()) / 1000);
            if (remaining <= 0) {
                cleanupExpiringNotification(symbol);
                return;
            }
            if (entry.messageEl) {
                entry.messageEl.innerHTML = buildExpiringCountdownMessage(symbol, remaining, entry.quantity);
            }
        };

        tick();
        entry.timerId = setInterval(tick, 1000);
    }

    function ensureExpiringNotification(symbol, quantity, secondsToExpiry) {
        const id = `expiring-${symbol}`;
        const shouldCountdown = secondsToExpiry <= EXPIRING_COUNTDOWN_THRESHOLD;
        const message = shouldCountdown
            ? buildExpiringCountdownMessage(symbol, secondsToExpiry, quantity)
            : buildExpiringWarningMessage(symbol, secondsToExpiry, quantity);

        let entry = expiringAssetNotifications.get(symbol);

        if (!entry) {
            const notification = showNotification(message, 'warning', {
                id,
                autoClose: false,
                onClose: () => cleanupExpiringNotification(symbol, { manual: true, skipRemove: true })
            });

            if (!notification) {
                return;
            }

            entry = {
                notification,
                messageEl: notification.querySelector('.notification-message'),
                timerId: null,
                mode: shouldCountdown ? 'countdown' : 'warning',
                expiryTimestamp: Date.now() + (secondsToExpiry * 1000),
                quantity
            };

            if (entry.notification) {
                entry.notification.className = 'notification notification-warning';
            }

            expiringAssetNotifications.set(symbol, entry);

            if (shouldCountdown) {
                startCountdownForEntry(symbol, entry);
            }

            return;
        }

        entry.expiryTimestamp = Date.now() + (secondsToExpiry * 1000);
        entry.quantity = quantity;

        if (!entry.messageEl || !entry.messageEl.isConnected) {
            entry.messageEl = entry.notification?.querySelector('.notification-message') || null;
        }

        if (entry.messageEl) {
            entry.messageEl.innerHTML = message;
        } else {
            const updatedNotification = showNotification(message, 'warning', {
                id,
                autoClose: false,
                replaceExisting: true
            });
            entry.notification = updatedNotification;
            entry.messageEl = updatedNotification?.querySelector('.notification-message') || null;
        }

        if (entry.notification) {
            entry.notification.className = 'notification notification-warning';
        }

        if (shouldCountdown) {
            if (entry.mode !== 'countdown') {
                entry.mode = 'countdown';
                startCountdownForEntry(symbol, entry);
            }
        } else {
            if (entry.timerId) {
                clearInterval(entry.timerId);
                entry.timerId = null;
            }
            entry.mode = 'warning';
        }
    }

    function cleanupExpiringNotification(symbol, options = {}) {
        const { manual = false, skipRemove = false } = options;
        const entry = expiringAssetNotifications.get(symbol);

        if (entry && entry.timerId) {
            clearInterval(entry.timerId);
        }

        if (!skipRemove) {
            removeNotificationById(`expiring-${symbol}`);
        }

        expiringAssetNotifications.delete(symbol);

        if (manual) {
            expiringNotificationSnoozed.set(symbol, Date.now() + EXPIRING_SNOOZE_MS);
        } else {
            expiringNotificationSnoozed.delete(symbol);
        }
    }

    function evaluateExpiringHoldings(assets) {
        if (!assets || !userPortfolio || !userPortfolio.holdings) {
            return;
        }

        const activeSymbols = new Set();
        const now = Date.now();

        Object.entries(userPortfolio.holdings).forEach(([symbol, quantity]) => {
            // Skip CASH - it's not an asset and never expires
            if (symbol.toUpperCase() === 'CASH') {
                return;
            }
            
            if (quantity <= 0) {
                return;
            }

            const assetInfo = assets[symbol];
            if (!assetInfo) {
                return;
            }

            const secondsToExpiry = Number(assetInfo.time_to_expiry_seconds);
            if (!Number.isFinite(secondsToExpiry)) {
                return;
            }

            if (secondsToExpiry <= 0) {
                cleanupExpiringNotification(symbol);
                return;
            }

            if (secondsToExpiry <= EXPIRING_NOTIFICATION_THRESHOLD) {
                const snoozedUntil = expiringNotificationSnoozed.get(symbol);
                if (snoozedUntil && snoozedUntil > now) {
                    return;
                }
                if (snoozedUntil && snoozedUntil <= now) {
                    expiringNotificationSnoozed.delete(symbol);
                }
                ensureExpiringNotification(symbol, quantity, secondsToExpiry);
                activeSymbols.add(symbol);
            }
        });

        expiringAssetNotifications.forEach((_, symbol) => {
            if (!activeSymbols.has(symbol)) {
                cleanupExpiringNotification(symbol);
            }
        });
    }

    function createTransactionRow(transaction, options = {}) {
        const { includeUser = false } = options;
        const resolvedSymbol = transaction.symbol || 'UNKNOWN';
        const colorHint = transaction.color ? transaction.color : null;
        const color = getInstrumentColor(resolvedSymbol, colorHint);
        const row = document.createElement('tr');
        row.className = `transaction-${transaction.type}`;

        const isSettlement = transaction.type === 'settlement';
        const typeColor = isSettlement ? '#f85149' : (transaction.type === 'buy' ? '#7dda58' : '#f85149');
        const typeText = isSettlement ? 'SETTLED' : (transaction.type || '').toUpperCase();

        const cells = [
            `<td data-label="Time" style="color: #94a3b8; font-size: 11px; white-space: nowrap;">${formatCompactDateTime(transaction.timestamp)}</td>`,
            `<td data-label="Symbol"><span class="symbol-badge" style="background-color: ${color};">${resolvedSymbol}</span></td>`,
            `<td data-label="Type" style="color: ${typeColor}; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">${typeText}</td>`,
            `<td data-label="Quantity" style="color: #e2e8f0; font-family: 'JetBrains Mono', monospace;">${formatQuantity(transaction.quantity)}</td>`,
            `<td data-label="Price" style="color: #00d4ff; font-family: 'JetBrains Mono', monospace;">${formatCurrencyLocale(transaction.price)}</td>`,
            `<td data-label="Total" style="color: #e2e8f0; font-family: 'JetBrains Mono', monospace; font-weight: 600;">${formatCurrencyLocale(transaction.total_cost)}</td>`
        ];

        if (includeUser) {
            cells.splice(2, 0, `<td data-label="User" style="color: #e2e8f0; font-family: 'JetBrains Mono', monospace;">${formatUserIdentifier(transaction.user_id)}</td>`);
        }

        row.innerHTML = cells.join('');
        return row;
    }

    function updateTransactionsTable() {
        if (!transactionsTableBody) return;

        transactionsTableBody.innerHTML = '';
        const sortedTransactions = sortTransactionsDescending(userTransactions);

        sortedTransactions.forEach(transaction => {
            const row = createTransactionRow(transaction);
            transactionsTableBody.appendChild(row);
        });
        
        // Update mobile transactions
        if (isMobileView()) {
            updateMobileTransactions(sortedTransactions);
        }
    }

    function updateAllTransactionsTable() {
        if (!allTransactionsTableBody) return;

        allTransactionsTableBody.innerHTML = '';
        const sortedTransactions = sortTransactionsDescending(globalTransactions);

        sortedTransactions.forEach(transaction => {
            const row = createTransactionRow(transaction, { includeUser: true });
            allTransactionsTableBody.appendChild(row);
        });
    }

    const LEADERBOARD_LIMIT = 50;
    let leaderboardEntries = [];
    let leaderboardRefreshTimer = null;

    function createLeaderboardRow(entry, index) {
        const totalPnl = Number(entry.total_pnl ?? 0);
        const row = document.createElement('tr');

        let stateClass = 'pnl-neutral';
        if (totalPnl > 0) {
            stateClass = 'pnl-positive';
        } else if (totalPnl < 0) {
            stateClass = 'pnl-negative';
        }
        row.classList.add(stateClass);

        const pnlColor = totalPnl > 0 ? '#7dda58' : totalPnl < 0 ? '#f85149' : '#94a3b8';
        const rankLabel = `#${index + 1}`;

        row.innerHTML = `
            <td data-label="Rank" style="color: #94a3b8; font-size: 11px; font-family: 'JetBrains Mono', monospace;">${rankLabel}</td>
            <td data-label="User ID" style="color: #e2e8f0; font-family: 'JetBrains Mono', monospace;">${entry.user_id}</td>
            <td data-label="Total P&L" style="color: ${pnlColor}; font-family: 'JetBrains Mono', monospace; font-weight: 600;">${formatCurrencyLocale(totalPnl)}</td>
        `;

        return row;
    }

    function updateLeaderboardTable() {
        if (!leaderboardTableBody) return;

        leaderboardTableBody.innerHTML = '';
        leaderboardEntries.forEach((entry, index) => {
            const row = createLeaderboardRow(entry, index);
            leaderboardTableBody.appendChild(row);
        });
    }

    function refreshLeaderboard(limit = LEADERBOARD_LIMIT) {
        if (!leaderboardTableBody) {
            return Promise.resolve();
        }

        return fetch(`/api/leaderboard?limit=${limit}`)
            .then(response => {
                if (response.status === 401) {
                    window.location.href = '/login';
                    return null;
                }
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (!data) {
                    return;
                }

                leaderboardEntries = Array.isArray(data)
                    ? data.map(entry => ({
                        user_id: entry.user_id,
                        total_pnl: Number(entry.total_pnl ?? 0)
                    }))
                    : [];

                updateLeaderboardTable();
                
                // Update mobile leaderboard
                if (isMobileView()) {
                    updateMobileLeaderboard(leaderboardEntries);
                }
            })
            .catch(error => {
                console.error('Error refreshing leaderboard:', error);
            });
    }

    function scheduleLeaderboardRefresh(delay = 2000) {
        if (!leaderboardTableBody) return;
        if (leaderboardRefreshTimer) return;

        leaderboardRefreshTimer = setTimeout(() => {
            leaderboardRefreshTimer = null;
            refreshLeaderboard();
        }, delay);
    }

    function sortTransactionsDescending(transactions) {
        if (!Array.isArray(transactions)) {
            return [];
        }

        return [...transactions].sort((a, b) => {
            const aTime = Number(a && a.timestamp != null ? a.timestamp : 0);
            const bTime = Number(b && b.timestamp != null ? b.timestamp : 0);
            if (bTime !== aTime) {
                return bTime - aTime;
            }

            const aSymbol = (a && a.symbol) ? String(a.symbol) : '';
            const bSymbol = (b && b.symbol) ? String(b.symbol) : '';
            if (aSymbol !== bSymbol) {
                return bSymbol.localeCompare(aSymbol);
            }

            const aType = (a && a.type) ? String(a.type) : '';
            const bType = (b && b.type) ? String(b.type) : '';
            return bType.localeCompare(aType);
        });
    }

    function normalizeTransaction(transaction) {
        if (!transaction) {
            return null;
        }

        const timestamp = typeof transaction.timestamp === 'number'
            ? transaction.timestamp
            : parseInt(transaction.timestamp, 10);

        return {
            timestamp: Number.isFinite(timestamp) ? timestamp : Date.now(),
            symbol: transaction.symbol || 'UNKNOWN',
            type: (transaction.type || 'trade').toLowerCase(),
            quantity: Number(transaction.quantity ?? 0),
            price: Number(transaction.price ?? 0),
            total_cost: Number(transaction.total_cost ?? 0),
            user_id: transaction.user_id ?? null,
            asset_id: transaction.asset_id ?? null,
            color: transaction.color ?? null
        };
    }

    function refreshGlobalTransactions(limit = GLOBAL_TRANSACTIONS_LIMIT) {
        return fetch(`/api/transactions/all?limit=${limit}`)
            .then(response => {
                if (response.status === 401) {
                    window.location.href = '/login';
                    return null;
                }
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (!data) {
                    return;
                }
                globalTransactions = data
                    .map(normalizeTransaction)
                    .filter(Boolean);
                updateAllTransactionsTable();
                scheduleLeaderboardRefresh(1000);
            })
            .catch(() => {
                // Swallow errors to avoid user-facing disruptions
            });
    }

    function updatePerformance() {
        fetch('/api/performance')
            .then(response => {
                // Check if user is not authenticated
                if (response.status === 401) {
                    // User session expired, redirect to login
                    window.location.href = '/login';
                    return null;
                }
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(performance => {
                if (!performance) return; // Skip if redirected
                
                // Update portfolio value
                portfolioValueEl.textContent = formatCurrencyLocale(performance.portfolio_value);
                if (!portfolioHistoryData.length) {
                    updatePortfolioHistoryLatestLabel(performance.portfolio_value);
                }
                
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
                    .then(response => {
                        if (response.status === 401) {
                            window.location.href = '/login';
                            return null;
                        }
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(portfolio => {
                        if (!portfolio) return;
                        setAvailableCash(portfolio.cash);
                    })
                    .catch(error => {
                        // Error fetching portfolio for cash
                    });
            })
            .catch(error => {
                // Error fetching performance data
                // Set fallback values to prevent NaN display
                portfolioValueEl.textContent = formatCurrencyLocale(100000);
                if (!portfolioHistoryData.length) {
                    updatePortfolioHistoryLatestLabel(100000);
                }
                totalPnlEl.textContent = formatCurrencyLocale(0);
                totalReturnEl.textContent = formatPercentage(0);
                realizedPnlEl.textContent = formatCurrencyLocale(0);
                unrealizedPnlEl.textContent = formatCurrencyLocale(0);
                setAvailableCash(100000);
            });
    }

    // Dynamic Chart Management System
    let chartInstances = []; // Array of chart objects
    let chartCount = 1; // Default number of charts
    let availableAssets = []; // Store available asset symbols for autocomplete
    let availableAssetDetails = {}; // Cache asset metadata (including colors)

    function initializeChartSystem() {
        // Load available assets for autocomplete
        fetch('/api/assets')
            .then(response => response.json())
            .then(assets => {
                availableAssetDetails = assets || {};
                availableAssets = Object.keys(assets).sort(); // Sort alphabetically

                // Seed instrument color cache using authoritative asset colors
                availableAssets.forEach(symbol => {
                    const assetData = availableAssetDetails[symbol];
                    if (assetData) {
                        getInstrumentColor(symbol, assetData);
                    }
                });
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

        const priceHeader = document.createElement('div');
        priceHeader.className = 'portfolio-value-header chart-price-header';

        const priceTitle = document.createElement('h3');
        priceTitle.className = 'chart-price-title';
        priceTitle.textContent = 'Last Prices';

        const priceDisplay = document.createElement('div');
        priceDisplay.className = 'portfolio-value-latest chart-price-latest';
        priceDisplay.id = `chart-price-display-${index}`;
        priceDisplay.textContent = '--';
        priceDisplay.classList.add('chart-price-latest-empty');

        // Canvas for the chart
        const canvas = document.createElement('canvas');
        canvas.id = `chart-canvas-${index}`;

        chartContainer.appendChild(controlsDiv);
        priceHeader.appendChild(priceTitle);
        priceHeader.appendChild(priceDisplay);
        chartContainer.appendChild(priceHeader);
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
                    titleColor: themeAccentColor,
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

                const sortedHistory = [...history].sort((a, b) => Number(a.time) - Number(b.time));
                const validHistory = [];
                let lastX = null;

                for (const point of sortedHistory) {
                    const time = Number(point?.time);
                    const price = Number(point?.price);
                    if (!Number.isFinite(time) || !Number.isFinite(price)) {
                        continue;
                    }

                    const formattedPoint = { x: time, y: price };
                    if (lastX !== null && time === lastX && validHistory.length) {
                        validHistory[validHistory.length - 1] = formattedPoint;
                    } else {
                        validHistory.push(formattedPoint);
                    }
                    lastX = time;
                }

                const assetData = availableAssetDetails[symbol] || null;
                const color = getInstrumentColor(symbol, assetData);
                
                const dataset = {
                    label: symbol,
                    data: validHistory,
                    borderColor: color,
                    backgroundColor: hexToRgba(color, 0.18),
                    fill: 'origin',
                    tension: 0.25,
                    cubicInterpolationMode: 'monotone',
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 6,
                    pointHoverBackgroundColor: color,
                    pointHoverBorderColor: '#0a0e1a',
                    pointHoverBorderWidth: 2,
                    stepped: false, // Ensure smooth line connections, not stepped
                    spanGaps: false, // Don't connect across missing data points
                    normalized: true
                };

                chartInstance.chart.data.datasets.push(dataset);
                chartInstance.chart.update('none'); // Update without animation for faster display

                // Force a redraw to ensure proper line rendering
                setTimeout(() => {
                    chartInstance.chart.update();
                }, 10);

                // Update symbols list display
                updateSymbolsList(chartIndex);
                updateChartLatestPrices(chartIndex);
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
        updateChartLatestPrices(chartIndex);
    }

    function clearChart(chartIndex) {
        const chartInstance = chartInstances[chartIndex];
        if (!chartInstance) return;

        chartInstance.symbols = [];
        chartInstance.chart.data.datasets = [];
        chartInstance.chart.update();
        updateSymbolsList(chartIndex);
        updateChartLatestPrices(chartIndex);
    }

    function updateSymbolsList(chartIndex) {
        const symbolsList = document.getElementById(`chart-symbols-${chartIndex}`);
        const chartInstance = chartInstances[chartIndex];
        
        if (!symbolsList || !chartInstance) return;

        symbolsList.innerHTML = chartInstance.symbols.map(symbol => {
            const assetData = availableAssetDetails[symbol] || null;
            const color = getInstrumentColor(symbol, assetData);
            return `
                <span class="chart-symbol-tag" style="background-color: ${color}20; border-left: 3px solid ${color};">
                    ${symbol}
                    <button class="remove-symbol-btn" onclick="removeSymbolFromChart(${chartIndex}, '${symbol}')">&times;</button>
                </span>
            `;
        }).join('');
    }

    function updateChartLatestPrices(chartIndex) {
        const displayEl = document.getElementById(`chart-price-display-${chartIndex}`);
        const chartInstance = chartInstances[chartIndex];

        if (!displayEl) {
            return;
        }

        if (!chartInstance || chartInstance.symbols.length === 0) {
            displayEl.textContent = '--';
            displayEl.classList.add('chart-price-latest-empty');
            return;
        }

        const formattedEntries = chartInstance.symbols.map(symbol => {
            const dataset = chartInstance.chart.data.datasets.find(ds => ds.label === symbol);
            let latestPrice = null;

            if (dataset && Array.isArray(dataset.data) && dataset.data.length > 0) {
                const lastPoint = dataset.data[dataset.data.length - 1];
                latestPrice = Number(lastPoint?.y);
            }

            if (!Number.isFinite(latestPrice) && latestAssetPrices[symbol] != null) {
                latestPrice = Number(latestAssetPrices[symbol]);
            }

            if (!Number.isFinite(latestPrice) && availableAssetDetails[symbol]?.price != null) {
                latestPrice = Number(availableAssetDetails[symbol].price);
            }

            if (!Number.isFinite(latestPrice)) {
                return `${symbol}: --`;
            }

            return `${symbol}: ${formatCurrencyLocale(latestPrice)}`;
        });

        if (formattedEntries.length === 0) {
            displayEl.textContent = '--';
            displayEl.classList.add('chart-price-latest-empty');
            return;
        }

        const hasValues = formattedEntries.some(entry => !entry.endsWith('--'));

        displayEl.textContent = formattedEntries.join(' | ');
        displayEl.classList.toggle('chart-price-latest-empty', !hasValues);
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
                        const needsResort = dataset.data.length > 1 && dataset.data[dataset.data.length - 1].x < dataset.data[dataset.data.length - 2].x;
                        if (needsResort) {
                            dataset.data.sort((a, b) => a.x - b.x);
                        }
                        const excess = dataset.data.length - 100;
                        if (excess > 0) {
                            dataset.data.splice(0, excess);
                        }
                    }
                    chartInstance.chart.update('none');
                    updateChartLatestPrices(chartInstance.index);
                }
            }
        });
    }

    // Initialize chart system on page load
    // Note: This will be called from the main DOMContentLoaded listener

    // Global function for removing symbols (called from onclick)
    window.removeSymbolFromChart = removeSymbolFromChart;

    // Helper function to detect mobile view
    function isMobileView() {
        // Use desktop layout in landscape orientation on mobile devices
        if (window.innerWidth <= 768 && window.matchMedia("(orientation: landscape)").matches) {
            return false;
        }
        return window.innerWidth <= 768;
    }

    // Function to handle symbol badge clicks - puts symbol in trade input
    function handleSymbolBadgeClick(symbol) {
        // Special handling for CASH
        if (symbol.toUpperCase() === 'CASH') {
            showNotification(
                'CASH represents your available balance to purchase assets with.',
                'info'
            );
            return;
        }
        
        const assetInput = document.getElementById('asset-input');
        if (assetInput) {
            assetInput.value = symbol.toUpperCase();
            assetInput.dispatchEvent(new Event('input'));
        }
    }

    // Function to handle mobile symbol badge clicks - navigates to asset
    function handleMobileSymbolBadgeClick(symbol) {
        // Special handling for CASH
        if (symbol.toUpperCase() === 'CASH') {
            showNotification(
                'CASH represents your available balance to purchase assets with.',
                'info'
            );
            return;
        }
        
        // Find the asset index
        const assetIndex = mobileAssets.findIndex(asset => asset.symbol === symbol);
        
        if (assetIndex !== -1) {
            // Asset exists - switch to assets tab and navigate to it
            const mobileTabs = document.querySelectorAll('.mobile-tab');
            const assetsTab = Array.from(mobileTabs).find(tab => tab.dataset.page === 'assets');
            
            if (assetsTab) {
                // Update active tab
                mobileTabs.forEach(t => t.classList.remove('active'));
                assetsTab.classList.add('active');
                
                // Show carousel, hide pages
                const mobileCarousel = document.getElementById('mobile-carousel');
                const mobilePages = document.querySelectorAll('.mobile-page');
                
                if (mobileCarousel) {
                    mobileCarousel.style.display = 'block';
                }
                
                mobilePages.forEach(p => p.classList.remove('active'));
                
                // Navigate to the asset
                currentMobileAssetIndex = assetIndex;
                updateMobileAssetDisplay();
            }
        } else {
            // Asset not found - likely expired
            showNotification(
                `Asset ${symbol} has expired and is no longer available for trading.`,
                'info'
            );
        }
    }

    // Function to add click handlers to all symbol badges
    function addSymbolBadgeClickHandlers() {
        // Add event delegation for dynamically created symbol badges
        document.addEventListener('click', function(e) {
            if (e.target.classList.contains('symbol-badge')) {
                const symbol = e.target.textContent.trim();
                
                // Check if mobile view - different behavior
                if (isMobileView()) {
                    handleMobileSymbolBadgeClick(symbol);
                } else {
                    handleSymbolBadgeClick(symbol);
                }
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

    // Initial load of transaction history and portfolio
    Promise.all([
        fetch('/api/transactions').then(response => response.json()),
        fetch('/api/portfolio').then(response => response.json())
    ]).then(([transactions, portfolio]) => {
        userTransactions = Array.isArray(transactions)
            ? transactions.map(normalizeTransaction).filter(Boolean)
            : [];
        userPortfolio = portfolio;
        currentUserId = portfolio.user_id; // Store user ID
        setAvailableCash(portfolio.cash);
        updateTransactionsTable();
        updatePortfolio();
        updatePerformance();
        refreshGlobalTransactions();
        refreshLeaderboard();
        refreshPortfolioHistory();
        
        // Update mobile transactions
        if (isMobileView()) {
            updateMobileTransactions(userTransactions);
        }
        
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
        schedulePortfolioHistoryRefresh(2000);
    });

    // Update performance on price changes (for unrealized P&L)
    socket.on('price_update', (assets) => {
        updateAssetsTable(assets);
        
        // Update portfolio holdings with new prices
        updatePortfolio();
        
        // Update performance as prices change to reflect current unrealized P&L
        updatePerformance();
        
        // Update pie chart with new portfolio values
        createOrUpdatePortfoliePieChart();
        schedulePortfolioHistoryRefresh(1500);
        
        // Update mobile view
        if (isMobileView()) {
            updateMobileAccountInfo();
            // If the overview panel is visible, update it first using the previous-price
            // snapshot so we compare against the authoritative previous price and avoid
            // overwriting that value before the comparison (this prevents a flash).
            if (mobileOverviewVisible) {
                try {
                    Object.entries(assets).forEach(([symbol, data]) => {
                        updateMobileOverviewSingle(symbol, { time: Date.now(), price: data.price });
                    });
                } catch (err) {
                    // ignore
                }
            }
            // Update header μ/σ stats for all assets in mobile view so header reflects
            // live statistics even when the overview panel is closed.
            try {
                Object.keys(assets).forEach(symbol => {
                    if (typeof updateMobileHeaderStats === 'function') {
                        updateMobileHeaderStats(symbol);
                    }
                });
            } catch (err) {
                // ignore
            }
            // Now update the mobile cards and authoritative previous-price store
            updateMobilePrices(assets);
            updateMobileExpiry(Object.values(assets), true); // Force update with fresh server data
            updateMobilePnL(); // Update P&L displays on asset cards
        }
    });

    function updateAssetsTable(assets) {
        latestAssetsSnapshot = assets;
        evaluateExpiringHoldings(assets);
        latestAssetPrices = {};
        
        // Update mobile view - only rebuild cards if asset list has changed
        if (isMobileView()) {
            const assetArray = Object.entries(assets).map(([symbol, data]) => ({
                symbol: symbol,
                price: data.price,
                color: data.color,
                expires_in: data.time_to_expiry_seconds || 0
            })).sort((a, b) => a.symbol.localeCompare(b.symbol));
            
            // Check if we need to rebuild cards (asset list changed)
            const currentSymbols = mobileAssets.map(a => a.symbol).sort().join(',');
            const newSymbols = assetArray.map(a => a.symbol).sort().join(',');
            
            if (currentSymbols !== newSymbols) {
                // Asset list changed, rebuild cards
                updateMobileAssets(assetArray);
            }
            // Note: price and expiry updates are handled separately by updateMobilePrices() and updateMobileExpiry()
        }
        
        // Fetch current open interest data
        fetch('/api/open-interest')
            .then(response => response.json())
            .then(openInterest => {
                openInterestData = openInterest;
                
                assetsTableBody.innerHTML = '';
                // Sort symbols alphabetically
                const sortedSymbols = Object.keys(assets).sort();
                for (const symbol of sortedSymbols) {
                    const assetData = assets[symbol];
                    const currentPrice = assetData.price;
                    latestAssetPrices[symbol] = currentPrice;
                    availableAssetDetails[symbol] = assetData;
                    const color = getInstrumentColor(symbol, assetData);
                    
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
                    
                    // Format expiration time
                    const timeToExpiry = assetData.time_to_expiry_seconds || 0;
                    const expiryDisplay = formatTimeToExpiry(timeToExpiry);
                    
                    const row = `<tr style="box-shadow: inset 3px 0 0 ${color};">
                        <td data-label="Symbol"><span class="symbol-badge" style="background-color: ${color};">${symbol}</span></td>
                        <td data-label="Price" style="color: ${priceColor}; font-weight: 600; font-family: 'JetBrains Mono', monospace;">${formatCurrencyLocale(currentPrice)}</td>
                        <td data-label="Expires In" style="font-family: 'JetBrains Mono', monospace;">${expiryDisplay}</td>
                        <td data-label="Open Interest" style="color: #94a3b8; font-family: 'JetBrains Mono', monospace;">${formatQuantity(totalOpenInterest)}</td>
                    </tr>`;
                    assetsTableBody.innerHTML += row;
                    
                    // Update price display for each chart
                    updatePriceDisplay(symbol);
                }

                chartInstances.forEach(instance => {
                    updateChartLatestPrices(instance.index);
                });
                
                // Reapply search filter after table update
                applyAssetSearchFilter();
                updateBuyingPowerDisplay();
                evaluateExpiringHoldings(assets);
            })
            .catch(error => {
                // Error fetching open interest
                
                // Fallback to showing just prices without open interest
                assetsTableBody.innerHTML = '';
                // Sort symbols alphabetically
                const sortedSymbols = Object.keys(assets).sort();
                for (const symbol of sortedSymbols) {
                    const assetData = assets[symbol];
                    const currentPrice = assetData.price;
                    latestAssetPrices[symbol] = currentPrice;
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
                    
                    // Format expiration time
                    const timeToExpiry = assetData.time_to_expiry_seconds || 0;
                    const expiryDisplay = formatTimeToExpiry(timeToExpiry);
                    
                    const row = `<tr style="box-shadow: inset 3px 0 0 ${color};">
                        <td data-label="Symbol"><span class="symbol-badge" style="background-color: ${color};">${symbol}</span></td>
                        <td data-label="Price" style="color: ${priceColor}; font-weight: 600; font-family: 'JetBrains Mono', monospace;">${formatCurrencyLocale(currentPrice)}</td>
                        <td data-label="Expires In" style="font-family: 'JetBrains Mono', monospace;">${expiryDisplay}</td>
                        <td data-label="Open Interest" style="color: #94a3b8; font-family: 'JetBrains Mono', monospace;">${formatQuantity(0)}</td>
                    </tr>`;
                    assetsTableBody.innerHTML += row;
                    
                    updatePriceDisplay(symbol);
                }

                chartInstances.forEach(instance => {
                    updateChartLatestPrices(instance.index);
                });
                
                // Reapply search filter after table update
                applyAssetSearchFilter();
                updateBuyingPowerDisplay();
                evaluateExpiringHoldings(assets);
            });
    }

    // Update charts with new price data
    socket.on('price_chart_update', (data) => {
        const { symbol, time, price } = data;
        updateChartData(symbol, {x: time, y: price});
        // NOTE: Do not update the mobile overview here — chart updates can arrive
        // independently and cause race conditions with the main `price_update`
        // handler which manages the authoritative previous-price store. The
        // overview is updated from the primary `price_update` handler instead.
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
                latestAssetPrices[symbol] = assets[symbol]?.price;
            }
            updateBuyingPowerDisplay();
        });

    // Update portfolio display
    function updatePortfolio() {
        fetch('/api/portfolio')
            .then(response => {
                // Check if user is not authenticated
                if (response.status === 401) {
                    // User session expired, redirect to login
                    window.location.href = '/login';
                    return null;
                }
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(portfolio => {
                if (!portfolio) return; // Skip if redirected
                
                userPortfolio = portfolio;
                setAvailableCash(portfolio.cash);
                
                // Update transactions if included in response
                if (Array.isArray(portfolio.transactions)) {
                    userTransactions = portfolio.transactions
                        .map(normalizeTransaction)
                        .filter(Boolean);
                    updateTransactionsTable();
                }
                
                cashBalance.textContent = formatNumber(portfolio.cash, 2);
                
                // Fetch current prices to calculate market values
                fetch('/api/assets')
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(assets => {
                        if (!assets) return;
                        latestAssetsSnapshot = assets;
                        evaluateExpiringHoldings(assets);
                        
                        holdingsList.innerHTML = '';
                        
                        // Get mobile holdings list if it exists
                        const mobileHoldingsList = document.getElementById('mobile-holdings-list');
                        if (mobileHoldingsList) {
                            mobileHoldingsList.innerHTML = '';
                        }
                        
                        // Add cash as the first item in holdings list
                        const cashColor = '#00d4ff'; // Cash color for consistency
                        const cashFormatted = formatNumber(portfolio.cash, 2);
                        const cashItem = `<li data-symbol="Cash" style="border-left: 3px solid ${cashColor}; padding-left: 12px; background: rgba(0, 0, 0, 0.3);">
                            <div class="holding-row">
                                <span class="symbol-badge" style="background-color: ${cashColor};">CASH</span>
                                <span class="cash-value holding-value holding-value-cash" title="$${cashFormatted}">$${cashFormatted}</span>
                            </div>
                        </li>`;
                        holdingsList.innerHTML += cashItem;
                        if (mobileHoldingsList) {
                            mobileHoldingsList.innerHTML += cashItem;
                        }
                        
                        // Add asset holdings
                        for (const symbol in portfolio.holdings) {
                            const quantity = portfolio.holdings[symbol];
                            if (quantity > 0) {
                                const color = getInstrumentColor(symbol);
                                const vwap = calculateVWAP(symbol);
                                
                                // Calculate market value using current price from assets or previousPrices
                                const currentPrice = assets[symbol]?.price || previousPrices[symbol];
                                const marketValue = currentPrice ? quantity * currentPrice : null;
                                
                                // Get P&L data if available
                                const pnlData = portfolio.position_pnl && portfolio.position_pnl[symbol];
                                const unrealizedPnl = pnlData ? pnlData.unrealized_pnl : null;
                                const unrealizedPnlPercent = pnlData ? pnlData.unrealized_pnl_percent : null;
                                
                                // Build the holding display with clear labels
                                const quantityDisplayValue = formatQuantity(quantity);
                const quantityDisplay = `<span class="holding-metric">
                                        <span class="holding-label">QTY:</span>
                    <span class="holding-value holding-value-qty" title="${quantityDisplayValue}">${quantityDisplayValue}</span>
                                    </span>`;
                                const marketValueFormatted = marketValue != null ? formatCurrencyLocale(marketValue) : null;
                                const marketValueDisplay = marketValueFormatted ? `<span class="holding-metric">
                                        <span class="holding-label">VALUE:</span>
                                        <span class="holding-value holding-value-amount" title="${marketValueFormatted}">${marketValueFormatted}</span>
                                    </span>` : '';
                                const vwapFormatted = vwap ? formatCurrencyLocale(vwap) : null;
                                const vwapDisplay = vwapFormatted ? `<span class="holding-metric">
                                        <span class="holding-label">VWAP:</span>
                                        <span class="holding-value holding-value-vwap" title="${vwapFormatted}">${vwapFormatted}</span>
                                    </span>` : '';
                                
                                // P&L display with color coding
                                let pnlDisplay = '';
                                if (unrealizedPnl !== null && unrealizedPnl !== undefined) {
                                    const pnlFormatted = formatCurrencyLocale(unrealizedPnl);
                                    const pnlPercentFormatted = formatPercentage(unrealizedPnlPercent);
                                    const pnlClass = unrealizedPnl >= 0 ? 'positive' : 'negative';
                                    pnlDisplay = `<span class="holding-metric">
                                        <span class="holding-label">P&L:</span>
                                        <span class="holding-value holding-value-pnl ${pnlClass}" title="${pnlFormatted} (${pnlPercentFormatted})">${pnlFormatted} (${pnlPercentFormatted})</span>
                                    </span>`;
                                }

                                const item = `<li data-symbol="${symbol}" style="border-left: 3px solid ${color}; padding-left: 12px; background: rgba(0, 0, 0, 0.3);">
                                    <div class="holding-row">
                                        <span class="symbol-badge" style="background-color: ${color};">${symbol}</span>
                                        ${quantityDisplay}${marketValueDisplay}${vwapDisplay}${pnlDisplay}
                                    </div>
                                </li>`;
                                holdingsList.innerHTML += item;
                                if (mobileHoldingsList) {
                                    mobileHoldingsList.innerHTML += item;
                                }
                            }
                        }
                        
                        // Update pie chart
                        createOrUpdatePortfoliePieChart();
                        
                        // Set up cross-highlighting after holdings list is updated
                        updateHoldingsCrossHighlighting();
                    })
                    .catch(error => {
                        // Error fetching assets for portfolio
                        if (latestAssetsSnapshot) {
                            evaluateExpiringHoldings(latestAssetsSnapshot);
                        }
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
        
        // Update mobile P&L displays
        updateMobilePnL();
        
        // Update mobile sell button state if on mobile view
        if (isMobileView() && mobileSellBtn && mobileAssets[currentMobileAssetIndex]) {
            const currentSymbol = mobileAssets[currentMobileAssetIndex].symbol;
            const hasPosition = userPortfolio.holdings && userPortfolio.holdings[currentSymbol] > 0;
            mobileSellBtn.disabled = !hasPosition;
            mobileSellBtn.style.opacity = hasPosition ? '1' : '0.5';
        }
        
        // Update assets table with new open interest data
        fetch('/api/assets')
            .then(response => response.json())
            .then(assets => {
                updateAssetsTable(assets);
            });
        scheduleLeaderboardRefresh(1500);
        schedulePortfolioHistoryRefresh(1200);
    });

    // Handle new transactions
    socket.on('transaction_added', (transaction) => {
        // Filter: only add if this transaction is for the current user (or no user_id specified for backward compatibility)
        if (!transaction.user_id || transaction.user_id === currentUserId) {
            // Refresh from API to get the latest data (same pattern as portfolio refresh)
            updatePortfolio();
            
            // Update VWAP line for this specific instrument
            updateVWAPLine(transaction.symbol);
        }
        scheduleLeaderboardRefresh(1000);
        schedulePortfolioHistoryRefresh(800);
    });

    socket.on('global_transaction_update', (transaction) => {
        const normalized = normalizeTransaction(transaction);
        if (!normalized) {
            return;
        }

        const existingIndex = globalTransactions.findIndex(item =>
            item.timestamp === normalized.timestamp &&
            item.symbol === normalized.symbol &&
            item.type === normalized.type &&
            item.total_cost === normalized.total_cost
        );

        if (existingIndex >= 0) {
            globalTransactions[existingIndex] = normalized;
        } else {
            globalTransactions = [normalized, ...globalTransactions];
        }

        if (globalTransactions.length > GLOBAL_TRANSACTIONS_LIMIT) {
            globalTransactions.length = GLOBAL_TRANSACTIONS_LIMIT;
        }

        updateAllTransactionsTable();
        scheduleLeaderboardRefresh(1000);
    });

    // Handle real-time performance updates
    socket.on('performance_update', () => {
        updatePerformance();
        scheduleLeaderboardRefresh(2000);
        schedulePortfolioHistoryRefresh(2000);
    });

    // Handle asset expiration and settlement events
    socket.on('assets_updated', (data) => {
        if (data.message) {
            showNotification(data.message, 'info');
        }
        
        if (data.stats && data.stats.settlement_stats) {
            const settleStats = data.stats.settlement_stats;
            const normalizedCurrentUserId = currentUserId != null ? String(currentUserId) : null;
            const settlementTransactions = Array.isArray(settleStats.transactions)
                ? settleStats.transactions
                : [];

            let userSettlements = [];
            if (normalizedCurrentUserId) {
                userSettlements = settlementTransactions.filter(tx => String(tx.user_id) === normalizedCurrentUserId);
            }

            if (userSettlements.length > 0) {
                const totalValue = userSettlements.reduce((sum, tx) => {
                    const raw = Number(tx.total_cost ?? tx.settlement_value ?? 0);
                    return Number.isFinite(raw) ? sum + raw : sum;
                }, 0);

                const uniqueSymbols = Array.from(new Set(userSettlements.map(tx => tx.symbol).filter(Boolean)));
                let symbolsSummary = '';
                if (uniqueSymbols.length > 0) {
                    const maxSymbols = 3;
                    const shownSymbols = uniqueSymbols.slice(0, maxSymbols);
                    symbolsSummary = shownSymbols.join(', ');
                    const remaining = uniqueSymbols.length - shownSymbols.length;
                    if (remaining > 0) {
                        symbolsSummary += `, +${remaining} more`;
                    }
                }

                let message = `${userSettlements.length} position${userSettlements.length === 1 ? '' : 's'} settled for ${formatCurrencyLocale(totalValue)}.`;
                if (symbolsSummary) {
                    message += ` (${symbolsSummary})`;
                }

                showNotification(message, 'success', { id: 'user-settlement-summary' });
            } else if (settlementTransactions.length === 0 && settleStats.positions_settled > 0) {
                // Fallback for older payloads without per-user transaction details
                showNotification(
                    `${settleStats.positions_settled} position(s) settled. Total value: ${formatCurrencyLocale(settleStats.total_value_settled)}`,
                    'success',
                    { id: 'user-settlement-summary' }
                );
            }
        }
        
        // Refresh all data after asset updates - fetch assets first to cache colors
        fetch('/api/assets')
            .then(response => response.json())
            .then(assets => {
                updateAssetsTable(assets);  // This caches the colors from asset data
                updatePortfolio();
                updatePerformance();
            })
            .catch(error => {
                // Error fetching assets
            });
        scheduleLeaderboardRefresh(2000);
        schedulePortfolioHistoryRefresh(2000);
    });

    // Handle portfolio refresh signal
    socket.on('portfolio_refresh_needed', () => {
        updatePortfolio();
        updatePerformance();
        createOrUpdatePortfoliePieChart();
        scheduleLeaderboardRefresh(1500);
        schedulePortfolioHistoryRefresh(1500);
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

        updateBuyingPowerDisplay();
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
        if (confirm(`Are you sure you want to sell ${positions.length} position(s)?`)) {
            // Disable the button to prevent double-clicking
            sellAllBtn.disabled = true;
            sellAllBtn.style.opacity = '0.6';
            sellAllBtn.style.cursor = 'not-allowed';
            
            let successCount = 0;
            let failCount = 0;
            
            tradeMessage.textContent = `Selling ${positions.length} position(s)... (0/${positions.length})`;
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
                    // Error selling position
                    failCount++;
                }
            }
            
            // Re-enable the button
            sellAllBtn.disabled = false;
            sellAllBtn.style.opacity = '1';
            sellAllBtn.style.cursor = 'pointer';
            
            // Show final result
            if (failCount === 0) {
                tradeMessage.textContent = `Successfully sold all ${successCount} position(s)!`;
                tradeMessage.style.color = '#7dda58'; // High contrast green
                tradeMessage.style.background = 'rgba(0, 255, 136, 0.1)';
                tradeMessage.style.border = '1px solid rgba(0, 255, 136, 0.3)';
            } else {
                tradeMessage.textContent = `Sold ${successCount}/${positions.length} position(s) (${failCount} failed)`;
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
        }
    });

    // Display trade confirmation messages
    socket.on('trade_confirmation', (data) => {
        // Show mobile toast notification instead of desktop message on mobile
        if (isMobileView()) {
            // Format the message with proper locale formatting for quantity
            let message = data.message;
            if (data.success && data.quantity && data.symbol) {
                const formattedQty = formatQuantity(data.quantity);
                const action = data.type === 'buy' ? 'Bought' : 'Sold';
                message = `${action} ${formattedQty} ${data.symbol}`;
            }
            
            // Use unified notification system
            showNotification(message, data.success ? 'success' : 'error');
        } else if (tradeMessage) {
            // Desktop message - only update if element exists
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
                if (tradeMessage) {
                    tradeMessage.textContent = '';
                    tradeMessage.style.background = '';
                    tradeMessage.style.border = '';
                }
            }, 3000);
        }
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

    // Initialize portfolio value chart and price charts
    createPortfolioValueChart();
    initializeChartSystem();

    // Set up symbol badge click handlers
    addSymbolBadgeClickHandlers();

    // Initial leaderboard load
    refreshLeaderboard();

    // ============================================
    // MOBILE VIEW FUNCTIONALITY
    // ============================================

    let mobileAssets = [];
    let currentMobileAssetIndex = 0;
    let mobileCharts = [];
    let touchStartY = 0;
    let touchEndY = 0;
    let isSwiping = false;
    let wheelTimeout = null;
    let wheelDeltaY = 0;
    let mobilePreviousPrices = {}; // Track price changes for color coding
    let mobileExpiryTimestamps = {}; // Track expiry timestamps for real-time countdown
    let assetHistories = {}; // Cached histories for overview stats
    let mobileOverviewVisible = false; // Is overview panel visible

    const mobileCarousel = document.getElementById('mobile-carousel');
    const mobilePortfolioValueEl = document.getElementById('mobile-portfolio-value');
    const mobileCashBalanceEl = document.getElementById('mobile-cash-balance');
    const mobileBuyBtn = document.getElementById('mobile-buy-btn');
    const mobileSellBtn = document.getElementById('mobile-sell-btn');
    const mobileSellAllBtn = document.getElementById('mobile-sell-all-btn');
    const mobileQuantityModal = document.getElementById('mobile-quantity-modal');
    const mobileQuantityInput = document.getElementById('mobile-quantity-input');
    const mobileQuantityTitle = document.getElementById('mobile-quantity-title');
    const mobileQuantityCancel = document.getElementById('mobile-quantity-cancel');
    const mobileQuantityConfirm = document.getElementById('mobile-quantity-confirm');

    let pendingMobileTrade = null;

    function initMobileView() {
        if (!isMobileView()) return;

        // Set up tab navigation
        const mobileTabs = document.querySelectorAll('.mobile-tab');
        const mobilePages = document.querySelectorAll('.mobile-page');

        mobileTabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const pageName = tab.dataset.page;
                
                // Update active tab
                mobileTabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');

                // Show/hide pages and carousel
                if (pageName === 'assets') {
                    mobileCarousel.style.display = 'block';
                    mobilePages.forEach(p => p.classList.remove('active'));
                    
                    // Trigger a small window scroll to activate Safari auto-hide
                    setTimeout(() => {
                        window.scrollTo(0, 1);
                    }, 100);
                } else {
                    mobileCarousel.style.display = 'none';
                    mobilePages.forEach(p => {
                        if (p.id === `mobile-page-${pageName}`) {
                            p.classList.add('active');
                        } else {
                            p.classList.remove('active');
                        }
                    });
                }
                // If the user left the 'assets' tab, hide the overview pane if open
                try {
                    const overviewPanel = document.getElementById('mobile-asset-overview');
                    const overviewToggle = document.getElementById('mobile-overview-toggle');
                    if (overviewPanel && overviewPanel.classList.contains('active') && pageName !== 'assets') {
                        overviewPanel.classList.remove('active');
                        if (overviewToggle) overviewToggle.setAttribute('aria-pressed', 'false');
                        mobileOverviewVisible = false;
                    }
                } catch (err) {
                    // ignore
                }
            });
        });

        // Set up touch handlers
        if (mobileCarousel) {
            mobileCarousel.addEventListener('touchstart', handleMobileTouchStart, { passive: true });
            mobileCarousel.addEventListener('touchmove', handleMobileTouchMove, { passive: false });
            mobileCarousel.addEventListener('touchend', handleMobileTouchEnd, { passive: true });
            
            // Note: Wheel/scroll navigation is completely disabled on mobile for better UX
            // Only touch swipe gestures navigate between asset cards
        }
        
        // Prevent actual scrolling while maintaining scroll position for Safari auto-hide
        window.addEventListener('scroll', () => {
            if (isMobileView() && window.scrollY !== 1) {
                window.scrollTo(0, 1);
            }
        }, { passive: true });

        // Set up trade buttons
        if (mobileBuyBtn) {
            mobileBuyBtn.addEventListener('click', () => handleMobileTrade('buy'));
        }

        if (mobileSellBtn) {
            mobileSellBtn.addEventListener('click', () => handleMobileTrade('sell'));
        }

        if (mobileSellAllBtn) {
            mobileSellAllBtn.addEventListener('click', handleMobileSellAll);
        }

        // Set up quantity modal
        if (mobileQuantityCancel) {
            mobileQuantityCancel.addEventListener('click', () => {
                mobileQuantityModal.classList.remove('active');
                pendingMobileTrade = null;
            });
        }

        if (mobileQuantityConfirm) {
            mobileQuantityConfirm.addEventListener('click', confirmMobileTrade);
        }

        // Set up mobile asset search
        const mobileAssetSearch = document.getElementById('mobile-asset-search');
        if (mobileAssetSearch) {
            mobileAssetSearch.addEventListener('input', (e) => {
                const searchTerm = e.target.value.toLowerCase().trim();
                if (!searchTerm) {
                    // Show current asset if search is cleared
                    return;
                }
                
                // Find matching asset
                const matchIndex = mobileAssets.findIndex(asset => 
                    asset.symbol.toLowerCase().includes(searchTerm)
                );
                
                if (matchIndex !== -1 && matchIndex !== currentMobileAssetIndex) {
                    currentMobileAssetIndex = matchIndex;
                    updateMobileAssetDisplay();
                }
            });
            // Hide overview when the user begins typing in search
            mobileAssetSearch.addEventListener('input', () => {
                const overviewPanel = document.getElementById('mobile-asset-overview');
                const toggle = document.getElementById('mobile-overview-toggle');
                if (overviewPanel && overviewPanel.classList.contains('active')) {
                    overviewPanel.classList.remove('active');
                    if (toggle) toggle.setAttribute('aria-pressed', 'false');
                    mobileOverviewVisible = false;
                }
            });
        }

        // Setup overview toggle (button inserted in template)
        const mobileOverviewToggle = document.getElementById('mobile-overview-toggle');
        const mobileOverviewPanel = document.getElementById('mobile-asset-overview');

        function computeReturnsStats(history) {
            // history: array of {time, price} sorted ascending
            if (!Array.isArray(history) || history.length < 2) {
                return { mean: 0, std: 0, count: 0 };
            }
            const returns = [];
            for (let i = 1; i < history.length; i++) {
                const p0 = Number(history[i - 1].price ?? history[i - 1].y ?? history[i - 1].price);
                const p1 = Number(history[i].price ?? history[i].y ?? history[i].price);
                if (!Number.isFinite(p0) || !Number.isFinite(p1) || p0 === 0) continue;
                const r = (p1 / p0 - 1) * 100.0; // percent returns
                returns.push(r);
            }

            const n = returns.length;
            if (n === 0) return { mean: 0, std: 0, count: 0 };

            const mean = returns.reduce((s, v) => s + v, 0) / n;
            const variance = n > 1 ? returns.reduce((s, v) => s + Math.pow(v - mean, 2), 0) / (n - 1) : 0;
            const std = Math.sqrt(variance);
            return { mean, std, count: n };
        }

        async function ensureHistoriesLoaded() {
            if (Object.keys(assetHistories).length > 0) return;
            try {
                const resp = await fetch('/api/assets/history');
                if (!resp.ok) return;
                const data = await resp.json();
                Object.entries(data).forEach(([symbol, history]) => {
                    // store as array of {time, price}
                    const normalized = (history || []).map(p => ({ time: Number(p.time), price: Number(p.price) })).filter(p => Number.isFinite(p.time) && Number.isFinite(p.price));
                    assetHistories[symbol] = normalized.slice(-200); // keep last 200 points
                });
            } catch (err) {
                // ignore
            }
        }

        function renderMobileAssetOverview() {
            const grid = document.getElementById('mobile-overview-grid');
            if (!grid) return;
            grid.innerHTML = '';

            // Use latestAssetsSnapshot if available, otherwise fetch /api/assets
            const assetsPromise = latestAssetsSnapshot ? Promise.resolve(latestAssetsSnapshot) : fetch('/api/assets').then(r => r.json()).catch(() => ({}));

            assetsPromise.then(async (assetsData) => {
                // Ensure histories loaded (may be async)
                await ensureHistoriesLoaded();

                const symbols = Object.keys(assetsData).sort();
                symbols.forEach(symbol => {
                    const a = assetsData[symbol] || {};
                    const color = getInstrumentColor(symbol, a);
                    const priceVal = a.price != null ? Number(a.price) : (mobilePreviousPrices[symbol] ?? latestAssetPrices[symbol] ?? 0);

                    // Prepare history for stats
                    const history = assetHistories[symbol] || [];
                    const stats = computeReturnsStats(history);

                    const card = document.createElement('div');
                    card.className = 'overview-card';

                    // If the user holds a position in this asset, add a highlight class
                    try {
                        const qty = (userPortfolio && userPortfolio.holdings && Number(userPortfolio.holdings[symbol])) || 0;
                        if (qty > 0) {
                            // Compute P&L if available
                            let pnl = null;
                            if (userPortfolio.position_pnl && userPortfolio.position_pnl[symbol]) {
                                pnl = Number(userPortfolio.position_pnl[symbol].unrealized_pnl ?? userPortfolio.position_pnl[symbol].total_pnl ?? null);
                            }
                            // Fallback: compute from VWAP if available and priceVal known
                            if (pnl === null) {
                                const vwap = calculateVWAP(symbol);
                                const currentPrice = Number(priceVal) || 0;
                                if (vwap && Number.isFinite(currentPrice)) {
                                    pnl = qty * (currentPrice - vwap);
                                }
                            }

                            card.classList.add('overview-has-position');
                            // Remove any existing profit/loss classes
                            card.classList.remove('overview-position-profit', 'overview-position-loss');
                            if (pnl !== null && Number.isFinite(pnl)) {
                                if (pnl > 0) card.classList.add('overview-position-profit');
                                else if (pnl < 0) card.classList.add('overview-position-loss');
                            }
                        }
                    } catch (err) {
                        // ignore
                    }

                    const btn = document.createElement('button');
                    btn.className = 'symbol-badge asset-overview-btn';
                    btn.style.backgroundColor = color;
                    btn.textContent = symbol;
                    btn.onclick = () => {
                        // emulate mobile symbol badge click behavior
                        // Hide overview after selecting an asset so user returns to the main mobile view
                        const overviewPanelHide = document.getElementById('mobile-asset-overview');
                        const overviewToggleBtn = document.getElementById('mobile-overview-toggle');
                        if (overviewPanelHide && overviewPanelHide.classList.contains('active')) {
                            overviewPanelHide.classList.remove('active');
                            overviewPanelHide.setAttribute('aria-hidden', 'true');
                        }
                        if (overviewToggleBtn) {
                            overviewToggleBtn.setAttribute('aria-pressed', 'false');
                        }
                        mobileOverviewVisible = false;
                        handleMobileSymbolBadgeClick(symbol);
                    };

                    const priceEl = document.createElement('div');
                    priceEl.className = 'overview-price';
                    priceEl.textContent = priceVal ? formatCurrencyLocale(priceVal) : '--';
                    // store the displayed previous price on the card so we can compare against it
                    // This avoids race conditions where `mobilePreviousPrices` is updated earlier
                    // by other handlers in the same socket event.
                    card.dataset.prevPrice = Number(priceVal) || 0;
                    // Apply coloring via CSS classes so the state persists reliably
                    try {
                        const prevNum = Number(card.dataset.prevPrice);
                        const prev = Number.isFinite(prevNum) && prevNum !== 0 ? prevNum : mobilePreviousPrices[symbol];
                        priceEl.classList.remove('price-up', 'price-down');
                        if (prev !== undefined && Number.isFinite(prev)) {
                            if (priceVal > prev) {
                                priceEl.classList.add('price-up');
                            } else if (priceVal < prev) {
                                priceEl.classList.add('price-down');
                            }
                        }
                        // clear any inline color so CSS classes determine appearance
                        priceEl.style.color = '';
                        // store previous price on the card for later comparisons
                        card.dataset.prevPrice = Number(priceVal) || 0;
                    } catch (err) {
                        // ignore
                    }

                    // (header stats population removed)

                    const statsEl = document.createElement('div');
                    statsEl.className = 'overview-stats';
                    const muClass = (Number(stats.mean) > 0) ? 'mu-positive' : 'mu-negative';
                    // sigma magnitude classification: <3% = low (green), 3-6% = mid (yellow), >=6% = high (red)
                    const sigmaVal = Number(stats.std);
                    let sigmaClass = 'sigma-low';
                    if (!Number.isFinite(sigmaVal)) {
                        sigmaClass = '';
                    } else if (Math.abs(sigmaVal) < 3) {
                        sigmaClass = 'sigma-low';
                    } else if (Math.abs(sigmaVal) < 6) {
                        sigmaClass = 'sigma-mid';
                    } else {
                        sigmaClass = 'sigma-high';
                    }
                    statsEl.innerHTML = `
                        <div class="overview-stat-row"><span class="overview-stat-label">μ</span><span class="overview-stat-value overview-mu ${muClass}">${formatNumber(stats.mean, 2)}%</span></div>
                        <div class="overview-stat-row"><span class="overview-stat-label">σ</span><span class="overview-stat-value overview-sigma ${sigmaClass}"><span class="overview-sigma-value">${formatNumber(stats.std, 2)}%</span><span class="overview-samples">n=${Number(stats.count || 0)}</span></span></div>
                    `;

                    card.appendChild(btn);
                    card.appendChild(priceEl);
                    card.appendChild(statsEl);

                    grid.appendChild(card);
                });
            });
        }

        function updateMobileOverviewSingle(symbol, newPricePoint) {
            // Update cached history
            if (!assetHistories[symbol]) assetHistories[symbol] = [];
            const arr = assetHistories[symbol];
            // Normalize point
            const time = Number(newPricePoint?.time ?? Date.now());
            const price = Number(newPricePoint?.price ?? newPricePoint?.y ?? newPricePoint?.price ?? newPricePoint);
            if (Number.isFinite(time) && Number.isFinite(price)) {
                arr.push({ time, price });
                if (arr.length > 200) arr.shift();
            }

            // Recompute stats and update DOM for that symbol
            const grid = document.getElementById('mobile-overview-grid');
            if (!grid) return;
            const cards = Array.from(grid.querySelectorAll('.overview-card'));
            for (const card of cards) {
                const btn = card.querySelector('.asset-overview-btn');
                if (btn && btn.textContent === symbol) {
                    const priceEl = card.querySelector('.overview-price');
                    const statsEl = card.querySelector('.overview-stats');
                    if (priceEl) priceEl.textContent = formatCurrencyLocale(price);
                    // Apply coloring via CSS classes so the state persists reliably
                    try {
                        const cardPrevRaw = card.dataset.prevPrice;
                        const cardPrev = Number.isFinite(Number(cardPrevRaw)) ? Number(cardPrevRaw) : undefined;
                        const prev = (cardPrev !== undefined && cardPrev !== 0) ? cardPrev : mobilePreviousPrices[symbol];
                        priceEl.classList.remove('price-up', 'price-down');
                        if (prev !== undefined && Number.isFinite(prev)) {
                            if (price > prev) {
                                priceEl.classList.add('price-up');
                            } else if (price < prev) {
                                priceEl.classList.add('price-down');
                            }
                        }
                        // clear any inline color so CSS classes determine appearance
                        priceEl.style.color = '';
                        // update the card's prevPrice to the new displayed price
                        card.dataset.prevPrice = price;
                    } catch (err) {
                        // ignore
                    }
                    // Also update the global mobilePreviousPrices so other parts of the UI stay consistent
                    mobilePreviousPrices[symbol] = price;
                    const stats = computeReturnsStats(arr);
                    if (statsEl) {
                        const muClass = (Number(stats.mean) > 0) ? 'mu-positive' : 'mu-negative';
                        const sigmaVal = Number(stats.std);
                        let sigmaClass = 'sigma-low';
                        if (!Number.isFinite(sigmaVal)) {
                            sigmaClass = '';
                        } else if (Math.abs(sigmaVal) < 3) {
                            sigmaClass = 'sigma-low';
                        } else if (Math.abs(sigmaVal) < 6) {
                            sigmaClass = 'sigma-mid';
                        } else {
                            sigmaClass = 'sigma-high';
                        }
                        statsEl.innerHTML = `
                            <div class="overview-stat-row"><span class="overview-stat-label">μ</span><span class="overview-stat-value overview-mu ${muClass}">${formatNumber(stats.mean, 2)}%</span></div>
                            <div class="overview-stat-row"><span class="overview-stat-label">σ</span><span class="overview-stat-value overview-sigma ${sigmaClass}"><span class="overview-sigma-value">${formatNumber(stats.std, 2)}%</span><span class="overview-samples">n=${Number(stats.count || 0)}</span></span></div>
                        `;
                    }
                    // (header-stats updating removed)
                    // Update highlight state for position (if holdings changed)
                    try {
                        const qtyNow = (userPortfolio && userPortfolio.holdings && Number(userPortfolio.holdings[symbol])) || 0;
                        if (qtyNow > 0) {
                            let pnlNow = null;
                            if (userPortfolio.position_pnl && userPortfolio.position_pnl[symbol]) {
                                pnlNow = Number(userPortfolio.position_pnl[symbol].unrealized_pnl ?? userPortfolio.position_pnl[symbol].total_pnl ?? null);
                            }
                            if (pnlNow === null) {
                                const vwapNow = calculateVWAP(symbol);
                                const currentPriceNow = Number(price) || 0;
                                if (vwapNow && Number.isFinite(currentPriceNow)) {
                                    pnlNow = qtyNow * (currentPriceNow - vwapNow);
                                }
                            }
                            card.classList.add('overview-has-position');
                            card.classList.remove('overview-position-profit', 'overview-position-loss');
                            if (pnlNow !== null && Number.isFinite(pnlNow)) {
                                if (pnlNow > 0) card.classList.add('overview-position-profit');
                                else if (pnlNow < 0) card.classList.add('overview-position-loss');
                            }
                        } else {
                            card.classList.remove('overview-has-position', 'overview-position-profit', 'overview-position-loss');
                        }
                    } catch (err) {
                        // ignore
                    }
                }
            }
        }

        // Update header stats helper: computes μ/σ from cached history and updates header snippet
        function updateMobileHeaderStats(symbol) {
            try {
                const headerStatsEl = document.getElementById(`mobile-stats-${symbol}`);
                if (!headerStatsEl) return;
                const history = assetHistories[symbol] || [];
                const stats = computeReturnsStats(history);
                const mu = Number(stats.mean || 0);
                const sigma = Number(stats.std || 0);
                const muClass = mu > 0 ? 'mu-positive' : 'mu-negative';
                let sigmaClass = '';
                if (Number.isFinite(sigma)) {
                    if (Math.abs(sigma) < 3) sigmaClass = 'sigma-low';
                    else if (Math.abs(sigma) < 6) sigmaClass = 'sigma-mid';
                    else sigmaClass = 'sigma-high';
                }
                headerStatsEl.innerHTML = `<span class="header-stat"><span class="header-stat-label">μ</span> <span class="header-stat-value overview-mu ${muClass}">${formatNumber(mu, 2)}%</span></span> <span class="header-stat-sep">|</span> <span class="header-stat"><span class="header-stat-label">σ</span> <span class="header-stat-value overview-sigma ${sigmaClass}">${formatNumber(sigma, 2)}%</span></span>`;
            } catch (err) {
                // ignore
            }
        }

        if (mobileOverviewToggle && mobileOverviewPanel) {
            mobileOverviewToggle.addEventListener('click', (e) => {
                mobileOverviewVisible = !mobileOverviewVisible;
                mobileOverviewPanel.classList.toggle('active', mobileOverviewVisible);
                mobileOverviewPanel.setAttribute('aria-hidden', String(!mobileOverviewVisible));
                mobileOverviewToggle.setAttribute('aria-pressed', String(!!mobileOverviewVisible));
                if (mobileOverviewVisible) {
                    // Render overview
                    renderMobileAssetOverview();
                }
            });
        }

        // Intercept touch events on the overview panel so they don't
        // propagate to the underlying carousel. Stop propagation only
        // (do not preventDefault) so native scrolling inside the
        // overview continues to work on mobile devices.
        if (mobileOverviewPanel) {
            ['touchstart', 'touchmove', 'touchend'].forEach((ev) => {
                mobileOverviewPanel.addEventListener(ev, function(e) {
                    if (mobileOverviewVisible) {
                        e.stopPropagation();
                        // Intentionally do NOT call preventDefault() here so
                        // the user can scroll the overview content normally.
                    }
                }, { passive: true });
            });
        }
        // Expose a couple helpers to the outer scope so real-time handlers can update the overview
        try {
            window.updateMobileOverviewSingle = updateMobileOverviewSingle;
            window.renderMobileAssetOverview = renderMobileAssetOverview;
            window.ensureAssetHistoriesLoaded = ensureHistoriesLoaded;
        } catch (err) {
            // ignore if window not writable in some contexts
        }

        // Initialize mobile data
        updateMobileAccountInfo();
        
        // Trigger initial window scroll to activate Safari auto-hide on page load
        setTimeout(() => {
            window.scrollTo(0, 1);
        }, 500);
        
        // Start real-time expiry countdown updates for mobile view
        setInterval(() => {
            if (isMobileView()) {
                updateMobileExpiryCountdown();
            }
        }, 1000);
    }

    function handleMobileTouchStart(e) {
        // If the overview is visible, ignore carousel touch handlers so
        // swipes inside the overview don't change the underlying card.
        if (mobileOverviewVisible) {
            touchStartY = 0;
            isSwiping = false;
            return;
        }

        touchStartY = e.touches[0].clientY;
        isSwiping = false;
        
        // // Keep window scroll position at 1px to maintain Safari auto-hide trigger
        // if (window.scrollY !== 1) {
        //     window.scrollTo(0, 1);
        // }
    }

    function handleMobileTouchMove(e) {
        // If the overview is visible, do not allow the carousel to react
        // to touch-move gestures.
        if (mobileOverviewVisible) {
            // Prevent default to stop any underlying scrolling behavior
            // and stop propagation (overview intercepts this elsewhere too).
            try { e.preventDefault(); } catch (err) {}
            return;
        }

        if (!touchStartY) return;
        
        touchEndY = e.touches[0].clientY;
        const diff = touchStartY - touchEndY;

        // Prevent default scrolling during swipe
        if (Math.abs(diff) > 10) {
            e.preventDefault();
            isSwiping = true;
        }
        
        // // Maintain window scroll position at 1px
        // if (window.scrollY !== 1) {
        //     window.scrollTo(0, 1);
        // }
    }

    function handleMobileTouchEnd(e) {
        // If the overview is visible, ignore touchend for carousel navigation
        if (mobileOverviewVisible) {
            touchStartY = 0;
            touchEndY = 0;
            isSwiping = false;
            // Ensure window scroll position remains consistent
            window.scrollTo(0, 1);
            return;
        }

        if (!isSwiping) {
            touchStartY = 0;
            touchEndY = 0;
            
            // Reset window scroll position
            window.scrollTo(0, 1);
            return;
        }

        const diff = touchStartY - touchEndY;
        const threshold = 50; // Minimum swipe distance

        if (Math.abs(diff) > threshold) {
            if (diff > 0) {
                // Swiped up - go to next asset
                navigateMobileAsset(1);
            } else {
                // Swiped down - go to previous asset
                navigateMobileAsset(-1);
            }
        }

        touchStartY = 0;
        touchEndY = 0;
        isSwiping = false;
        
        // Reset window scroll position after swipe
        window.scrollTo(0, 1);
    }

    function handleMobileWheel(e) {
        // Only handle wheel events when on the assets tab
        const assetsTab = document.querySelector('.mobile-tab[data-page="assets"]');
        if (!assetsTab || !assetsTab.classList.contains('active')) {
            return;
        }

        e.preventDefault();
        
        // Accumulate wheel delta
        wheelDeltaY += e.deltaY;
        
        // Clear existing timeout
        if (wheelTimeout) {
            clearTimeout(wheelTimeout);
        }
        
        // Set a short timeout to debounce rapid wheel events
        wheelTimeout = setTimeout(() => {
            const threshold = 100; // Minimum accumulated delta to trigger navigation
            
            if (Math.abs(wheelDeltaY) > threshold) {
                if (wheelDeltaY > 0) {
                    // Scrolled down - go to next asset
                    navigateMobileAsset(1);
                } else {
                    // Scrolled up - go to previous asset
                    navigateMobileAsset(-1);
                }
            }
            
            // Reset accumulator
            wheelDeltaY = 0;
        }, 150); // Wait 150ms after last wheel event
    }

    function navigateMobileAsset(direction) {
        if (mobileAssets.length === 0) return;

        const newIndex = currentMobileAssetIndex + direction;
        
        if (newIndex < 0 || newIndex >= mobileAssets.length) {
            return; // Don't wrap around
        }

        currentMobileAssetIndex = newIndex;
        updateMobileAssetDisplay();
    }

    function createMobileAssetCard(asset, index) {
        const card = document.createElement('div');
        card.className = 'mobile-asset-card';
        card.dataset.index = index;

        const assetColor = getInstrumentColor(asset.symbol, asset);

        // Calculate expiry text (styling will be applied by updateMobileExpiry)
        let expiryText = 'Loading...';
        if (asset.expires_in !== undefined) {
            const seconds = Math.floor(asset.expires_in);
            if (seconds < 60) {
                expiryText = `Expires in ${seconds}s`;
            } else if (seconds < 300) {
                const hours = Math.floor(seconds / 3600);
                const minutes = Math.floor((seconds % 3600) / 60);
                expiryText = hours > 0 ? `Expires in ${hours}h ${minutes}m` : `Expires in ${minutes}m`;
            } else {
                const hours = Math.floor(seconds / 3600);
                const minutes = Math.floor((seconds % 3600) / 60);
                expiryText = hours > 0 ? `Expires in ${hours}h ${minutes}m` : `Expires in ${minutes}m`;
            }
        }
        
        // Check if user has a position in this asset
        const hasPosition = userPortfolio.holdings && userPortfolio.holdings[asset.symbol] > 0;
        let positionHtml = '';
        
        if (hasPosition) {
            const quantity = userPortfolio.holdings[asset.symbol];
            const vwap = calculateVWAP(asset.symbol);
            const pnlData = userPortfolio.position_pnl && userPortfolio.position_pnl[asset.symbol];
            
            let positionInfo = `<div class="mobile-asset-position" id="mobile-position-${asset.symbol}">`;
            positionInfo += `<span class="mobile-position-label">Position:</span> <span class="mobile-position-qty">${formatQuantity(quantity)}</span>`;
            
            if (vwap) {
                positionInfo += ` <span class="mobile-position-separator">|</span> <span class="mobile-position-label">VWAP:</span> <span class="mobile-position-vwap">${formatCurrencyLocale(vwap)}</span>`;
            }
            
            if (pnlData) {
                const unrealizedPnl = pnlData.unrealized_pnl;
                const unrealizedPnlPercent = pnlData.unrealized_pnl_percent;
                const pnlClass = unrealizedPnl >= 0 ? 'positive' : 'negative';
                const pnlFormatted = formatCurrencyLocale(unrealizedPnl);
                const pnlPercentFormatted = formatPercentage(unrealizedPnlPercent);
                positionInfo += ` <span class="mobile-position-separator">|</span> <span class="mobile-position-label">P&L:</span> <span class="mobile-position-pnl ${pnlClass}">${pnlFormatted} (${pnlPercentFormatted})</span>`;
            }
            
            positionInfo += `</div>`;
            positionHtml = positionInfo;
        }

        card.innerHTML = `
            <div class="mobile-asset-header">
                <div class="mobile-asset-symbol">${asset.symbol}</div>
                <div class="mobile-asset-price" id="mobile-price-${asset.symbol}">$${asset.price ? asset.price.toFixed(2) : '0.00'}</div>
                ${positionHtml}
                <div class="mobile-asset-expiry">
                    <span class="mobile-expiry-label">Expires In:</span>
                    <span id="mobile-expiry-${asset.symbol}">${expiryText}</span>
                    <span class="mobile-header-stats" id="mobile-stats-${asset.symbol}">
                        <!-- μ and σ will be filled in if history available -->
                    </span>
                </div>
            </div>
            <div class="mobile-asset-chart">
                <canvas id="mobile-chart-${asset.symbol}"></canvas>
            </div>
        `;
        // Set the color of the symbol to the asset's associated color
        const symbolEl = card.querySelector('.mobile-asset-symbol');
        if (symbolEl) {
            symbolEl.style.color = getInstrumentColor(asset.symbol, asset);
        }

        return card;
    }

    function updateMobileAssets(assets) {
        if (!isMobileView() || !mobileCarousel) return;

        // Store the currently displayed symbol before updating
        const currentSymbol = mobileAssets[currentMobileAssetIndex]?.symbol;

        // Build a map of new asset symbols
        const newAssetSymbols = new Set(assets.map(a => a.symbol));
        // Build a map of current asset symbols
        const currentAssetSymbols = new Set(mobileAssets.map(a => a.symbol));

        // Remove cards for assets that have expired
        const cards = mobileCarousel.querySelectorAll('.mobile-asset-card');
        cards.forEach(card => {
            const symbol = card.querySelector('.mobile-asset-symbol')?.textContent;
            if (symbol && !newAssetSymbols.has(symbol)) {
                // Remove chart for this symbol
                const chartIdx = mobileCharts.findIndex(c => c.symbol === symbol);
                if (chartIdx !== -1) {
                    if (mobileCharts[chartIdx].chart) {
                        mobileCharts[chartIdx].chart.destroy();
                    }
                    mobileCharts.splice(chartIdx, 1);
                }
                card.remove();
            }
        });

        // Add cards for new assets
        assets.forEach((asset, index) => {
            if (!currentAssetSymbols.has(asset.symbol)) {
                const card = createMobileAssetCard(asset, index);
                // Insert in correct order
                // Find the next card (by index) to insert before
                let inserted = false;
                const allCards = mobileCarousel.querySelectorAll('.mobile-asset-card');
                for (let i = 0; i < allCards.length; i++) {
                    const cardSymbol = allCards[i].querySelector('.mobile-asset-symbol')?.textContent;
                    const newIdx = assets.findIndex(a => a.symbol === cardSymbol);
                    if (newIdx > index) {
                        mobileCarousel.insertBefore(card, allCards[i]);
                        inserted = true;
                        break;
                    }
                }
                if (!inserted) {
                    mobileCarousel.appendChild(card);
                }
                // Create chart for this asset
                const canvas = card.querySelector(`#mobile-chart-${asset.symbol}`);
                if (canvas) {
                    createMobileAssetChart(canvas, asset);
                }
            }
        });

        // Update mobileAssets to the new list
        mobileAssets = assets;
        // Keep a snapshot for the overview renderer to avoid refetching
        try {
            latestAssetsSnapshot = Array.isArray(assets) ? Object.fromEntries(assets.map(a => [a.symbol, a])) : latestAssetsSnapshot;
        } catch (err) {
            // ignore
        }

        // Try to maintain the same symbol if it still exists
        if (currentSymbol) {
            const newIndex = mobileAssets.findIndex(a => a.symbol === currentSymbol);
            if (newIndex !== -1) {
                // Symbol still exists, stay on it
                currentMobileAssetIndex = newIndex;
            } else {
                // Symbol no longer exists (expired), adjust index if needed
                if (currentMobileAssetIndex >= mobileAssets.length) {
                    currentMobileAssetIndex = Math.max(0, mobileAssets.length - 1);
                }
            }
        } else {
            // No previous symbol, reset to 0
            currentMobileAssetIndex = 0;
        }

        // Initialize expiry timestamps and styling for all assets
        updateMobileExpiry(mobileAssets, true);

        // Update display without animations to prevent visual glitches
        updateMobileAssetDisplay(true);

        // If the mobile overview is open, re-render it so it reflects
        // the current asset list (including expired/added assets).
        try {
            if (mobileOverviewVisible) {
                renderMobileAssetOverview();
            }
        } catch (err) {
            // ignore
        }
    }

    function updateMobileAssetDisplay(skipAnimation = false) {
        const cards = mobileCarousel.querySelectorAll('.mobile-asset-card');
        
        // Temporarily disable transitions to prevent glitches during rebuild
        if (skipAnimation) {
            mobileCarousel.style.transition = 'none';
            cards.forEach(card => {
                card.style.transition = 'none';
            });
        }
        
        cards.forEach((card, index) => {
            card.classList.remove('active', 'prev', 'next');
            
            if (index === currentMobileAssetIndex) {
                card.classList.add('active');
            } else if (index < currentMobileAssetIndex) {
                card.classList.add('prev');
            } else {
                card.classList.add('next');
            }
        });

        // Re-enable transitions after layout is complete
        if (skipAnimation) {
            // Use requestAnimationFrame to ensure layout is complete before re-enabling transitions
            requestAnimationFrame(() => {
                mobileCarousel.style.transition = '';
                cards.forEach(card => {
                    card.style.transition = '';
                });
            });
        }       

        // Update sell button state
        if (mobileSellBtn && mobileAssets[currentMobileAssetIndex]) {
            const currentSymbol = mobileAssets[currentMobileAssetIndex].symbol;
            const hasPosition = userPortfolio.holdings && userPortfolio.holdings[currentSymbol] > 0;
            mobileSellBtn.disabled = !hasPosition;
            mobileSellBtn.style.opacity = hasPosition ? '1' : '0.5';
        }

        // Hide tooltips for all mobile charts (including the active one)
        mobileCharts.forEach(chartObj => {
            if (chartObj && chartObj.chart) {
                chartObj.chart.setActiveElements([]);
                if (chartObj.chart.tooltip) {
                    chartObj.chart.tooltip.setActiveElements([], {x: 0, y: 0});
                }
                chartObj.chart.update('none');
            }
        });
    }

    function createMobileAssetChart(canvas, asset) {
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        const assetColor = getInstrumentColor(asset.symbol, asset);

        // Remove any existing chart for this symbol to avoid duplicates
        const existingIndex = mobileCharts.findIndex(c => c.symbol === asset.symbol);
        if (existingIndex !== -1) {
            // Destroy the old chart instance
            if (mobileCharts[existingIndex].chart) {
                mobileCharts[existingIndex].chart.destroy();
            }
            mobileCharts.splice(existingIndex, 1);
        }

        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                datasets: [{
                    label: asset.symbol,
                    data: [],
                    borderColor: assetColor,
                    backgroundColor: hexToRgba(assetColor, 0.1),
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'minute',
                            displayFormats: {
                                minute: 'HH:mm'
                            }
                        },
                        grid: {
                            color: 'rgba(148, 163, 184, 0.1)',
                            drawBorder: false
                        },
                        ticks: {
                            color: '#94a3b8',
                            font: {
                                size: 10,
                                family: 'JetBrains Mono'
                            }
                        }
                    },
                    y: {
                        grid: {
                            color: 'rgba(148, 163, 184, 0.1)',
                            drawBorder: false
                        },
                        ticks: {
                            color: '#94a3b8',
                            font: {
                                size: 10,
                                family: 'JetBrains Mono'
                            },
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(7, 8, 10, 0.95)',
                        titleColor: '#f5f7fa',
                        bodyColor: '#94a3b8',
                        borderColor: assetColor,
                        borderWidth: 1,
                        padding: 12,
                        displayColors: false,
                        callbacks: {
                            label: function(context) {
                                return '$' + context.parsed.y.toFixed(2);
                            }
                        }
                    },
                    annotation: {
                        annotations: {}
                    }
                }
            }
        });

        mobileCharts.push({ symbol: asset.symbol, chart: chart });

        // Update VWAP line if user has position
        updateMobileVWAPLine(asset.symbol);

        // Load historical data with timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout

        fetch(`/api/assets/history?symbol=${asset.symbol}`, {
            signal: controller.signal
        })
            .then(response => {
                clearTimeout(timeoutId);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data && data[asset.symbol]) {
                    const history = data[asset.symbol].map(point => ({
                        x: new Date(point.time),
                        y: point.price
                    }));
                    chart.data.datasets[0].data = history;
                    chart.update('none');
                    
                    // Update VWAP line after historical data is loaded
                    updateMobileVWAPLine(asset.symbol);
                }
            })
            .catch(error => {
                clearTimeout(timeoutId);
                // Silently ignore abort errors and network errors (timeout/fetch failures)
                // AbortError: timeout triggered
                // TypeError: network error or fetch failure
                if (error.name !== 'AbortError' && !(error instanceof TypeError)) {
                    console.warn(`Could not load history for ${asset.symbol}:`, error.message);
                }
            });
    }

    function updateMobileVWAPLine(symbol) {
        if (!isMobileView()) return;
        
        const chartObj = mobileCharts.find(c => c.symbol === symbol);
        if (!chartObj || !chartObj.chart) return;
        
        const chart = chartObj.chart;
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
                    display: true,
                    position: 'start', // Position at start for better visibility
                    backgroundColor: 'rgba(0, 212, 255, 0.95)', // More opaque for better readability
                    color: '#0a0e1a',
                    font: {
                        family: 'JetBrains Mono, Consolas, Monaco, monospace',
                        size: 10, // Slightly larger for mobile
                        weight: 700
                    },
                    padding: {
                        top: 4,
                        bottom: 4,
                        left: 6,
                        right: 6
                    },
                    borderRadius: 4,
                    yAdjust: 0
                }
            };
        } else {
            // Remove VWAP line if no current position
            delete chart.options.plugins.annotation.annotations.vwapLine;
        }
        chart.update('none');
    }

    function updateMobileAccountInfo() {
        if (!isMobileView()) return;

        // Update from desktop elements
        if (portfolioValueEl && mobilePortfolioValueEl) {
            mobilePortfolioValueEl.textContent = portfolioValueEl.textContent;
        }

        if (availableCashEl && mobileCashBalanceEl) {
            mobileCashBalanceEl.textContent = availableCashEl.textContent;
        }

        // Update performance page
        const perfMap = {
            'mobile-portfolio-value-perf': portfolioValueEl,
            'mobile-total-pnl': totalPnlEl,
            'mobile-total-return': totalReturnEl,
            'mobile-realized-pnl': realizedPnlEl,
            'mobile-unrealized-pnl': unrealizedPnlEl
        };

        Object.entries(perfMap).forEach(([mobileId, desktopEl]) => {
            const mobileEl = document.getElementById(mobileId);
            if (mobileEl && desktopEl) {
                mobileEl.textContent = desktopEl.textContent;
                mobileEl.className = desktopEl.className;
            }
        });
        
        // Update mobile portfolio chart
        updateMobilePortfolioChart();
    }

    function createMobilePortfolioChart() {
        if (mobilePortfolioChart) {
            return mobilePortfolioChart;
        }

        const canvas = document.getElementById('mobile-portfolio-chart');
        if (!canvas) {
            return null;
        }

        const ctx = canvas.getContext('2d');
        const accent = themeAccentColor || '#3b82f6';
        const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height || 250);
        gradient.addColorStop(0, `${accent}33`);
        gradient.addColorStop(1, `${accent}00`);

        mobilePortfolioChart = new Chart(ctx, {
            type: 'line',
            data: {
                datasets: [{
                    label: 'Portfolio Value',
                    data: [],
                    borderColor: accent,
                    backgroundColor: gradient,
                    fill: 'origin',
                    tension: 0.2,
                    cubicInterpolationMode: 'monotone',
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    pointHoverBorderWidth: 2,
                    pointHoverBorderColor: '#0a0e1a',
                    pointHoverBackgroundColor: accent,
                    spanGaps: true,
                    normalized: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        enabled: true,
                        backgroundColor: 'rgba(10, 14, 26, 0.95)',
                        titleColor: '#94a3b8',
                        bodyColor: '#e2e8f0',
                        borderColor: 'rgba(148, 163, 184, 0.2)',
                        borderWidth: 1,
                        padding: 12,
                        displayColors: false,
                        callbacks: {
                            title: function(context) {
                                const date = new Date(context[0].parsed.x);
                                return date.toLocaleString();
                            },
                            label: function(context) {
                                return formatCurrencyLocale(context.parsed.y);
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'hour',
                            displayFormats: {
                                hour: 'MMM d, ha'
                            }
                        },
                        grid: {
                            color: 'rgba(148, 163, 184, 0.08)',
                            drawBorder: false
                        },
                        ticks: {
                            color: '#64748b',
                            font: {
                                size: 10,
                                family: "'IBM Plex Sans', sans-serif"
                            },
                            maxRotation: 0,
                            autoSkipPadding: 20
                        }
                    },
                    y: {
                        grid: {
                            color: 'rgba(148, 163, 184, 0.08)',
                            drawBorder: false
                        },
                        ticks: {
                            color: '#64748b',
                            font: {
                                size: 10,
                                family: "'IBM Plex Sans', sans-serif"
                            },
                            callback: function(value) {
                                return formatCurrencyLocale(value);
                            }
                        }
                    }
                }
            }
        });

        return mobilePortfolioChart;
    }

    function updateMobilePortfolioChart() {
        if (!isMobileView()) return;
        
        const chart = createMobilePortfolioChart();
        if (!chart) {
            return;
        }

        // Use the same portfolio history data as desktop
        chart.data.datasets[0].data = portfolioHistoryData.slice();
        chart.update('none');
        
        // Update the latest value display
        const latestValueEl = document.getElementById('mobile-chart-latest');
        if (latestValueEl && portfolioHistoryData.length > 0) {
            const latestValue = portfolioHistoryData[portfolioHistoryData.length - 1].y;
            latestValueEl.textContent = formatCurrencyLocale(latestValue);
        }
    }

    function updateMobilePrices(prices) {
        if (!isMobileView()) return;

        Object.entries(prices).forEach(([symbol, data]) => {
            const priceEl = document.getElementById(`mobile-price-${symbol}`);
            if (priceEl) {
                const currentPrice = data.price;
                priceEl.textContent = formatCurrencyLocale(currentPrice);
                
                // Apply color based on price change (match desktop behavior)
                if (mobilePreviousPrices[symbol] !== undefined) {
                    if (currentPrice > mobilePreviousPrices[symbol]) {
                        priceEl.style.color = '#7dda58'; // Bright green for increase
                    } else if (currentPrice < mobilePreviousPrices[symbol]) {
                        priceEl.style.color = '#f85149'; // Bright red for decrease
                    } else {
                        priceEl.style.color = 'var(--terminal-accent)'; // Neutral
                    }
                }
                
                // Store current price for next comparison
                mobilePreviousPrices[symbol] = currentPrice;
                
                // Update the mobileAssets array with latest price
                const assetIndex = mobileAssets.findIndex(a => a.symbol === symbol);
                if (assetIndex !== -1) {
                    mobileAssets[assetIndex].price = currentPrice;
                }
            }

            // Update chart if it exists
            const chartObj = mobileCharts.find(c => c.symbol === symbol);
            if (chartObj && chartObj.chart) {
                const newPoint = {
                    x: new Date(),
                    y: data.price
                };
                chartObj.chart.data.datasets[0].data.push(newPoint);
                
                // Keep last 100 points
                if (chartObj.chart.data.datasets[0].data.length > 100) {
                    chartObj.chart.data.datasets[0].data.shift();
                }
                
                chartObj.chart.update('none');
                
                // Update VWAP line for this symbol
                updateMobileVWAPLine(symbol);
            }
        });
        
        // Update mobile buying power display if modal is open
        if (mobileQuantityModal && mobileQuantityModal.classList.contains('active')) {
            updateMobileBuyingPower();
        }
    }

    function updateMobilePnL() {
        if (!isMobileView()) return;

        // Iterate through all assets and update position info
        mobileAssets.forEach(asset => {
            const positionEl = document.getElementById(`mobile-position-${asset.symbol}`);
            const hasPosition = userPortfolio.holdings && userPortfolio.holdings[asset.symbol] > 0;
            
            // If position element exists but user no longer has position, remove it
            if (positionEl && !hasPosition) {
                positionEl.remove();
                return;
            }
            
            // If user has position but element doesn't exist, recreate the card
            if (hasPosition && !positionEl) {
                // Find the card and regenerate it
                const cards = document.querySelectorAll('.mobile-asset-card');
                cards.forEach((card, index) => {
                    const symbolEl = card.querySelector('.mobile-asset-symbol');
                    if (symbolEl && symbolEl.textContent === asset.symbol) {
                        const newCard = createMobileAssetCard(asset, index);
                        card.replaceWith(newCard);
                        // Always create the chart, not just for the active asset
                        const canvas = newCard.querySelector(`#mobile-chart-${asset.symbol}`);
                        if (canvas) {
                            createMobileAssetChart(canvas, asset);
                        }
                    }
                });
                return;
            }
            
            // Update existing position element
            if (positionEl && hasPosition) {
                const quantity = userPortfolio.holdings[asset.symbol];
                const vwap = calculateVWAP(asset.symbol);
                const pnlData = userPortfolio.position_pnl && userPortfolio.position_pnl[asset.symbol];
                
                let positionInfo = `<span class="mobile-position-label">Position:</span> <span class="mobile-position-qty">${formatQuantity(quantity)}</span>`;
                
                if (vwap) {
                    positionInfo += ` <span class="mobile-position-separator">|</span> <span class="mobile-position-label">VWAP:</span> <span class="mobile-position-vwap">${formatCurrencyLocale(vwap)}</span>`;
                }
                
                if (pnlData) {
                    const unrealizedPnl = pnlData.unrealized_pnl;
                    const unrealizedPnlPercent = pnlData.unrealized_pnl_percent;
                    const pnlClass = unrealizedPnl >= 0 ? 'positive' : 'negative';
                    const pnlFormatted = formatCurrencyLocale(unrealizedPnl);
                    const pnlPercentFormatted = formatPercentage(unrealizedPnlPercent);
                    positionInfo += ` <span class="mobile-position-separator">|</span> <span class="mobile-position-label">P&L:</span> <span class="mobile-position-pnl ${pnlClass}">${pnlFormatted} (${pnlPercentFormatted})</span>`;
                }
                
                positionEl.innerHTML = positionInfo;
            }
        });
        
        // Update VWAP lines for all mobile charts
        mobileCharts.forEach(chartObj => {
            updateMobileVWAPLine(chartObj.symbol);
        });
    }

    function updateMobileExpiry(assets, forceUpdate = false) {
        if (!isMobileView()) return;

        assets.forEach(asset => {
            const expiryEl = document.getElementById(`mobile-expiry-${asset.symbol}`);
            if (!expiryEl) return;
            
            // Support both expires_in (from mobileAssets) and time_to_expiry_seconds (from socket updates)
            const expirySeconds = asset.expires_in !== undefined ? asset.expires_in : asset.time_to_expiry_seconds;
            
            // When we receive fresh expiry data, store the expiry timestamp
            if (expirySeconds !== undefined && forceUpdate) {
                mobileExpiryTimestamps[asset.symbol] = Date.now() + (expirySeconds * 1000);
            }
            
            // Calculate remaining time from stored timestamp
            let seconds = 0;
            if (mobileExpiryTimestamps[asset.symbol]) {
                seconds = Math.max(0, Math.floor((mobileExpiryTimestamps[asset.symbol] - Date.now()) / 1000));
            } else if (expirySeconds !== undefined) {
                // Fallback if we don't have a timestamp yet
                seconds = Math.floor(expirySeconds);
                mobileExpiryTimestamps[asset.symbol] = Date.now() + (seconds * 1000);
            } else {
                return;
            }
            
            // Use the same formatTimeToExpiry function as desktop Assets table
            expiryEl.innerHTML = formatTimeToExpiry(seconds);
        });
    }

    function updateMobileExpiryCountdown() {
        if (!isMobileView()) return;
        
        // Update all assets based on stored timestamps
        Object.keys(mobileExpiryTimestamps).forEach(symbol => {
            const expiryEl = document.getElementById(`mobile-expiry-${symbol}`);
            if (!expiryEl) return;
            
            const seconds = Math.max(0, Math.floor((mobileExpiryTimestamps[symbol] - Date.now()) / 1000));
            
            // Use the same formatTimeToExpiry function as desktop Assets table
            expiryEl.innerHTML = formatTimeToExpiry(seconds);
        });
    }

    function handleMobileTrade(tradeType) {
        if (!mobileAssets[currentMobileAssetIndex]) return;

        const asset = mobileAssets[currentMobileAssetIndex];
        
        pendingMobileTrade = {
            symbol: asset.symbol,
            type: tradeType
        };

        mobileQuantityTitle.textContent = `${tradeType === 'buy' ? 'Buy' : 'Sell'} ${asset.symbol}`;
        const quantityHeld = userPortfolio.holdings && userPortfolio.holdings[asset.symbol] ? userPortfolio.holdings[asset.symbol] : 0;
        // mobileQuantityInput.value = quantityHeld;
        // if (tradeType === 'sell') mobileQuantityInput.value = quantityHeld
        // else mobileQuantityInput.value = '';
        mobileQuantityInput.value = tradeType === 'sell' ? quantityHeld : '';
        mobileQuantityInput.placeholder = tradeType === 'buy' ? 'Enter quantity' : 'Enter quantity';
        
        // Update buying power display
        updateMobileBuyingPower();
        
        mobileQuantityModal.classList.add('active');
        
        // Focus input (no need to change body overflow as body is already fixed on mobile)
        setTimeout(() => mobileQuantityInput.focus(), 100);
    }

    function updateMobileBuyingPower() {
        if (!mobileAssets[currentMobileAssetIndex]) return;
        
        const asset = mobileAssets[currentMobileAssetIndex];
        const currentPrice = asset.price || 0;
        const isSelling = pendingMobileTrade && pendingMobileTrade.type === 'sell';
        
        const bpCashEl = document.getElementById('mobile-bp-cash');
        const bpPriceEl = document.getElementById('mobile-bp-price');
        const bpSharesEl = document.getElementById('mobile-bp-shares');
        
        // Get the label elements
        const bpCashLabelEl = document.querySelector('.mobile-bp-row:nth-child(1) .mobile-bp-label');
        const bpSharesLabelEl = document.querySelector('.mobile-bp-row:nth-child(3) .mobile-bp-label');
        
        if (isSelling) {
            // When selling, show holdings information
            const holdingQuantity = userPortfolio?.holdings?.[asset.symbol] || 0;
            const holdingValue = holdingQuantity * currentPrice;
            
            if (bpCashLabelEl) bpCashLabelEl.textContent = 'Holdings Value:';
            if (bpCashEl) bpCashEl.textContent = holdingQuantity > 0 ? formatCurrencyLocale(holdingValue) : formatCurrencyLocale(0);
            
            if (bpPriceEl) bpPriceEl.textContent = currentPrice > 0 ? formatCurrencyLocale(currentPrice) : '--';
            
            if (bpSharesLabelEl) bpSharesLabelEl.textContent = 'Shares Held:';
            if (bpSharesEl) bpSharesEl.textContent = holdingQuantity > 0 ? formatNumber(holdingQuantity, 0) : '0';
        } else {
            // When buying, show buying power information
            if (bpCashLabelEl) bpCashLabelEl.textContent = 'Available Cash:';
            if (bpCashEl) bpCashEl.textContent = mobileCashBalanceEl ? mobileCashBalanceEl.textContent : formatCurrencyLocale(0);
            
            if (bpPriceEl) bpPriceEl.textContent = currentPrice > 0 ? formatCurrencyLocale(currentPrice) : '--';
            
            if (bpSharesLabelEl) bpSharesLabelEl.textContent = 'Max Shares:';
            if (bpSharesEl && currentPrice > 0 && availableCashAmount > 0) {
                const maxShares = Math.floor(availableCashAmount / currentPrice);
                bpSharesEl.textContent = formatNumber(maxShares, 0);
            } else if (bpSharesEl) {
                bpSharesEl.textContent = '--';
            }
        }
    }

    function confirmMobileTrade() {
        if (!pendingMobileTrade) return;

        const quantity = parseFloat(mobileQuantityInput.value);
        
        if (isNaN(quantity) || quantity <= 0) {
            alert('Please enter a valid quantity');
            return;
        }

        socket.emit('trade', {
            symbol: pendingMobileTrade.symbol,
            type: pendingMobileTrade.type,
            quantity: quantity
        });

        mobileQuantityModal.classList.remove('active');
        pendingMobileTrade = null;
        mobileQuantityInput.value = '';
    }

    async function handleMobileSellAll() {
        if (!userPortfolio || !userPortfolio.holdings) return;
        
        const positions = Object.entries(userPortfolio.holdings).filter(([symbol, quantity]) => quantity > 0);
        
        if (positions.length === 0) {
            showNotification('No positions to sell', 'warning');
            return;
        }
        
        // Confirm sell all
        if (!confirm(`Are you sure you want to sell all ${positions.length} position(s)?`)) {
            return;
        }
        
        // Disable button during processing
        if (mobileSellAllBtn) {
            mobileSellAllBtn.disabled = true;
            mobileSellAllBtn.style.opacity = '0.6';
        }
        
        let successCount = 0;
        let failCount = 0;
        
        showNotification(`Selling ${positions.length} positions... (0/${positions.length})`, 'info', { id: 'sell-all-progress' });
        
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
                        removeNotificationById('sell-all-progress');
                        showNotification(`Selling ${positions.length} positions... (${completed}/${positions.length})`, 'info', { id: 'sell-all-progress' });
                        resolve();
                    });
                });
                
                // Small delay between trades to prevent overwhelming the server
                if (i < positions.length - 1) {
                    await new Promise(resolve => setTimeout(resolve, 200));
                }
            } catch (error) {
                failCount++;
            }
        }
        
        // Re-enable button
        if (mobileSellAllBtn) {
            mobileSellAllBtn.disabled = false;
            mobileSellAllBtn.style.opacity = '1';
        }
        
        // Remove progress notification
        removeNotificationById('sell-all-progress');
        
        // Show final result
        if (failCount === 0) {
            showNotification(`Successfully sold all ${successCount} position(s)!`, 'success');
        } else {
            showNotification(`Sold ${successCount}/${positions.length} position(s) (${failCount} failed)`, 'warning');
        }
    }

    function updateMobileTransactions(transactions) {
        if (!isMobileView()) return;

        const tbody = document.querySelector('#mobile-transactions-table tbody');
        if (!tbody) return;

        tbody.innerHTML = '';

        transactions.slice(0, 50).forEach(tx => {
            const row = document.createElement('tr');
            row.className = `transaction-${tx.type}`;
            
            const date = new Date(tx.timestamp);
            const timeStr = date.toLocaleTimeString('en-US', { 
                hour: '2-digit', 
                minute: '2-digit'
            });

            // Color coding for transaction type matching desktop
            const isSettlement = tx.type === 'settlement';
            const typeColor = isSettlement ? '#f85149' : (tx.type === 'buy' ? '#7dda58' : '#f85149');
            const typeText = isSettlement ? 'SETTLED' : (tx.type || '').toUpperCase();

            row.innerHTML = `
                <td>${timeStr}</td>
                <td><span class="symbol-badge">${tx.symbol}</span></td>
                <td style="color: ${typeColor}; font-weight: 600;">${typeText}</td>
                <td>${formatQuantity(tx.quantity)}</td>
                <td>${formatCurrencyLocale(tx.price)}</td>
            `;

            tbody.appendChild(row);
        });
    }

    function updateMobileLeaderboard(leaderboard) {
        if (!isMobileView()) return;

        const tbody = document.querySelector('#mobile-leaderboard-table tbody');
        if (!tbody) return;

        tbody.innerHTML = '';

        leaderboard.forEach((entry, index) => {
            const row = document.createElement('tr');
            
            const totalPnl = Number(entry.total_pnl ?? 0);
            
            let className = 'pnl-neutral';
            let pnlColor = '#94a3b8';
            
            if (totalPnl > 0) {
                className = 'pnl-positive';
                pnlColor = '#7dda58'; // Green for profit
            } else if (totalPnl < 0) {
                className = 'pnl-negative';
                pnlColor = '#f85149'; // Red for loss
            }
            
            row.className = className;

            row.innerHTML = `
                <td>${index + 1}</td>
                <td>${entry.user_id}</td>
                <td style="color: ${pnlColor}; font-weight: 600;">${formatCurrencyLocale(totalPnl)}</td>
            `;

            tbody.appendChild(row);
        });
    }

    // Initialize mobile view if needed
    if (isMobileView()) {
        initMobileView();
    }

    // Listen for window resize
    window.addEventListener('resize', () => {
        if (isMobileView() && mobileCarousel && mobileCarousel.children.length === 0) {
            initMobileView();
            if (latestAssetsSnapshot) {
                updateMobileAssets(latestAssetsSnapshot);
            }
        }
    });
});
