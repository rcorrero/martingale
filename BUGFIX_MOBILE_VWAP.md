# Bug Fix: Mobile VWAP Line Not Appearing After Buying Second Asset

## Problem Description

When a user buys a second asset (or any asset after already owning one), the VWAP line would not appear on the newly purchased asset's chart, and the chart would stop updating with new price data.

## Root Causes

### Issue #1: Missing VWAP Update After History Load
When historical data loaded asynchronously and updated the chart, the VWAP annotation was not re-applied, causing it to disappear.

### Issue #2: Duplicate Chart Instances (PRIMARY ISSUE)
When `updateMobilePnL()` recreated a card with position info, it would create a new chart but NOT remove the old chart reference from the `mobileCharts` array. This caused:
1. Multiple chart instances for the same symbol in the array
2. `updateMobileVWAPLine()` using `.find()` would find the OLD destroyed chart
3. VWAP updates being applied to the wrong (destroyed) chart instance
4. The new chart never receiving VWAP annotations or price updates

### Issue #3: Lazy Chart Creation
Charts were only created for the currently displayed asset, not for all assets with positions, causing charts to be missing when navigating to newly purchased assets.

## Solution

### Fix #1: Update VWAP After History Loads
Added call to `updateMobileVWAPLine()` after historical data is loaded.

### Fix #2: Prevent Duplicate Chart Instances (PRIMARY FIX)
Added cleanup logic in `createMobileAssetChart()` to:
1. Check if a chart already exists for the symbol
2. Destroy the old chart instance properly
3. Remove it from the `mobileCharts` array
4. Then create the new chart

### Fix #3: Always Create Charts for Positions
Removed the conditional that only created charts for the currently viewed asset.

## Code Changes

### Change #1: Duplicate Prevention
**File**: `/Users/richardcorrero/Projects/martingale/static/js/main.js`
**Location**: Line ~3442, `createMobileAssetChart` function

```javascript
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
        // ... chart config
    });
    // ...
}
```

### Change #2: VWAP After History Load
**Location**: Line ~3560, history fetch callback

```javascript
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
```

### Change #3: Always Create Charts
**Location**: Line ~3868, `updateMobilePnL` function

```javascript
// Always create the chart, not just for the active asset
const canvas = newCard.querySelector(`#mobile-chart-${asset.symbol}`);
if (canvas) {
    createMobileAssetChart(canvas, asset);
}
```

## Why This Works

The primary issue was that `mobileCharts` array contained stale chart references. When buying a second asset:

1. User buys Asset B → Portfolio updates
2. `updateMobilePnL()` recreates Asset B's card
3. **OLD**: New chart created, old chart left in array → duplicates!
4. **NEW**: Old chart destroyed and removed, then new chart created ✓
5. VWAP updates now target the correct (new) chart instance
6. Price updates flow to the correct chart
7. Charts remain functional for all assets

## Testing Checklist

To verify the fix:

- [ ] Buy Asset A → VWAP line appears ✓
- [ ] Navigate to Asset A in mobile carousel → VWAP line visible ✓
- [ ] Buy Asset B (while viewing Asset A) → Both charts functional ✓
- [ ] Navigate to Asset B → VWAP line appears ✓
- [ ] Navigate back to Asset A → VWAP line still visible ✓
- [ ] Price updates continue to flow to both charts ✓
- [ ] Buy more of Asset A → VWAP updates correctly ✓
- [ ] Buy Asset C → All three charts functional ✓
- [ ] Sell entire position → VWAP disappears ✓

## Related Files

- `/Users/richardcorrero/Projects/martingale/static/js/main.js` (all fixes)
- `/Users/richardcorrero/Projects/martingale/MOBILE_VWAP_FEATURE.md` (original feature docs)
- `/Users/richardcorrero/Projects/martingale/docs/MOBILE_VWAP_VISUAL_GUIDE.md` (visual guide)

## Deployment

```bash
git add static/js/main.js BUGFIX_MOBILE_VWAP.md
git commit -m "Fix: Mobile VWAP duplicate chart instances and missing updates"
git push heroku main
```
