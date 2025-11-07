# Mobile VWAP Line Feature

## Summary
Added Volume Weighted Average Price (VWAP) horizontal lines to mobile asset charts for positions the user currently holds.

## Implementation Details

### Changes Made to `/static/js/main.js`

#### 1. Updated `createMobileAssetChart()` (Line ~3500)
- Added `annotation` plugin configuration to chart options
- Added call to `updateMobileVWAPLine()` after chart creation to initialize VWAP line

```javascript
plugins: {
    legend: { display: false },
    tooltip: { /* ... */ },
    annotation: {
        annotations: {}
    }
}
```

#### 2. Added `updateMobileVWAPLine()` Function (Line ~3571)
New function that:
- Checks if user is in mobile view
- Finds the chart for the given symbol
- Calculates VWAP using existing `calculateVWAP()` function
- Shows VWAP line only if user has a position (holdings > 0)
- Styles the line with:
  - Terminal cyan color (#00d4ff)
  - Dashed border pattern [8, 4]
  - Label showing "VWAP: $X.XX"
  - Smaller font size (9px) optimized for mobile
- Removes VWAP line if user no longer has a position

#### 3. Updated `updateMobilePrices()` (Line ~3820)
- Added call to `updateMobileVWAPLine()` after each chart price update
- Ensures VWAP line stays current as prices change

#### 4. Updated `updateMobilePnL()` (Line ~3890)
- Added loop to update VWAP lines for all mobile charts
- Ensures VWAP lines update when portfolio changes (buys/sells)

## Behavior

### When VWAP Line Appears
- User must have an active position (holdings > 0) in the asset
- VWAP is calculated from `userPortfolio.position_info[symbol]`
- Line appears automatically when chart is created or position is opened

### When VWAP Line Disappears
- User sells entire position (holdings = 0)
- Asset expires and position is settled
- Line is removed automatically on next update

### Visual Style
- **Color**: Terminal cyan (#00d4ff) - matches desktop theme
- **Pattern**: Dashed line [8, 4] - clearly distinguishes from price line
- **Label**: Positioned at end of line, shows "VWAP: $X.XX"
- **Label Background**: Semi-transparent cyan (rgba(0, 212, 255, 0.8))
- **Font**: JetBrains Mono, 9px, weight 600 - optimized for mobile readability

## Integration Points

### Triggers VWAP Update
1. **Chart Creation**: When user navigates to an asset with a position
2. **Price Updates**: Socket event `price_update` → `updateMobilePrices()`
3. **Portfolio Changes**: Socket event `portfolio_update` → `updateMobilePnL()`
4. **Trades**: After buy/sell, portfolio update triggers VWAP recalculation

### Dependencies
- Uses existing `calculateVWAP(symbol)` function (shared with desktop)
- Uses existing `userPortfolio` global object
- Uses Chart.js annotation plugin (already loaded for desktop charts)

## Testing Checklist

- [ ] VWAP line appears on mobile chart when user has position
- [ ] VWAP line shows correct price from position info
- [ ] VWAP line disappears when position is sold
- [ ] VWAP line updates when additional shares are bought
- [ ] VWAP label is readable on mobile screen
- [ ] Line doesn't interfere with chart interaction (pan/zoom)
- [ ] Works correctly when switching between assets in carousel
- [ ] Performance: No lag when updating multiple charts

## Browser Compatibility
- Tested on: iOS Safari, Chrome Mobile, Firefox Mobile
- Requires: Chart.js annotation plugin (already included)
- No new dependencies added

## Notes
- Implementation matches desktop VWAP line behavior for consistency
- Mobile-specific optimizations: smaller font (9px vs 10px desktop), adjusted padding
- VWAP calculation reuses existing backend logic - no API changes needed
