# Strategy Log

## Fundamental Overlay Integration
All base strategies (Final Target List, Swing List, Super List) are now enriched with the following strategy inputs:

1. **Catalyst Boost**: A string keyword flag ("Yes"/"No"). When "Yes", it indicates recent corporate press releases have positive keywords (e.g., "order", "acquisition", "financial results"). This validates technical breakouts.
2. **Event Risk**: Measures the countdown (`Days to Event`) to an upcoming Board Meeting or AGM. Highly relevant for GTT entry setups (Swing Strategy) to prevent buying directly into binary earnings risk.
3. **Insider Score**: Aggregates SEBI Reg 7 Insider filings over the last 30 days:
   - +3: Huge Promoter Buying
   - +1: Standard Promoter Buying
   - -2: Promoter Selling
   - -3: Pledge Increase
   - This score acts as a "Smart Money" footprint validator.
