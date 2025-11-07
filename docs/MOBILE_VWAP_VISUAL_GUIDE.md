# Mobile VWAP Line Visual Reference

## Chart Appearance

When viewing an asset in the mobile carousel where the user has a position:

```
┌─────────────────────────────────────┐
│  BTC                        $45,234 │  <- Asset header
│  Position: 10 | VWAP: $44,500       │  <- Position info
├─────────────────────────────────────┤
│                                     │
│  $46,000 ┬─────────────────────────│
│          │     ╱╲                   │
│  $45,000 ┤    ╱  ╲    ╱─────       │  <- Price line (solid, colored)
│          │   ╱    ╲  ╱              │
│  $44,500 ┼ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄VWAP │  <- VWAP line (dashed cyan)
│          │  ╱      ╲╱               │     with label at end
│  $44,000 ┴─────────────────────────│
│         10:00  11:00  12:00  13:00  │
└─────────────────────────────────────┘
```

## VWAP Line Styling

### Line Properties
- **Color**: `#00d4ff` (Terminal Cyan)
- **Width**: `2px`
- **Pattern**: Dashed `[8px dash, 4px gap]`
- **Horizontal**: Spans full chart width at VWAP price level

### Label Properties
- **Position**: End of line (right side)
- **Text**: "VWAP: $XX,XXX.XX" (formatted currency)
- **Background**: `rgba(0, 212, 255, 0.8)` (semi-transparent cyan)
- **Text Color**: `#0a0e1a` (dark, for contrast)
- **Font**: JetBrains Mono, 9px, weight 600
- **Padding**: 3px
- **Border Radius**: 3px

## Color Scheme Match

The VWAP line uses the same terminal cyan color as other UI elements:
- Matches desktop VWAP implementation
- Complements the theme's accent colors
- Stands out clearly against the dark background
- Doesn't conflict with profit/loss colors (green/red)

## Visibility Conditions

### VWAP Line SHOWS when:
✅ User has position (holdings > 0)
✅ Position info available in portfolio
✅ Chart successfully loaded

### VWAP Line HIDDEN when:
❌ User has no position (holdings = 0)
❌ Position was just sold
❌ Asset expired and settled
❌ Portfolio not yet loaded

## Example Scenarios

### Scenario 1: User Buys Asset
1. User navigates to asset (no VWAP line)
2. User buys 100 shares at $50.00
3. Chart updates → VWAP line appears at $50.00
4. Label shows "VWAP: $50.00"

### Scenario 2: User Adds to Position
1. User already holds 100 shares, VWAP at $50.00
2. User buys 100 more shares at $55.00
3. Chart updates → VWAP line moves to $52.50
4. Label updates to "VWAP: $52.50"

### Scenario 3: User Sells Entire Position
1. User holds position with VWAP line visible
2. User sells all shares
3. Chart updates → VWAP line disappears
4. Only price line remains

## Mobile Optimization

### Touch Interaction
- VWAP line doesn't interfere with chart gestures
- User can still pan/zoom chart normally
- Label positioned at edge to minimize obstruction

### Performance
- Updates use `chart.update('none')` for smooth animation
- No redraw when unnecessary (position hasn't changed)
- Minimal CPU usage on mobile devices

### Responsive Design
- Font size optimized for mobile (9px vs 10px desktop)
- Label padding reduced for smaller screens (3px vs 4px)
- Maintains readability on all mobile screen sizes
