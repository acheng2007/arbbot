> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Market Structure

> Understand how Polymarket US markets use a single instrument per outcome

Each market on Polymarket US has **one instrument** representing a specific outcome. You take positions by buying or selling (shorting) that single instrument.

## How It Works

Every binary market has only **one instrument**:

* **Buying the instrument** = taking the YES side of that outcome
* **Selling (shorting) the instrument** = taking the NO side of that outcome

**Example**: NFL game between Team A and Team B

* There is one instrument: "Team A wins"
* **Go long** (buy) = you think Team A will win
* **Go short** (sell) = you think Team A will lose (Team B wins)

## Buying vs Shorting

**Buying (Going Long)**

* You pay the current price (e.g., \$0.70)
* If the outcome happens, you receive \$1.00
* If the outcome doesn't happen, you receive \$0.00
* Maximum profit: \$1.00 minus purchase price
* Maximum loss: your purchase price

**Shorting (Going Short)**

* You receive the current price (e.g., \$0.70)
* If the outcome happens, you pay \$1.00
* If the outcome doesn't happen, you pay \$0.00
* Maximum profit: sale price
* Maximum loss: \$1.00 minus sale price

<Note>
  For more details on shorting mechanics, see [Collateral and Margin](/market-structure/collateral-and-margin#shorting-mechanics).
</Note>

## Synthetic No Position

There are no separate "No" shares to trade. Instead:

* To take the NO side of an outcome, you **short** the instrument
* Shorting creates a synthetic NO position
* The profit/loss works exactly as if you owned a NO share

## Key Points

* Each market has **one instrument** per outcome
* **Buy** to take the YES side, **short** to take the NO side
* There are no separate YES and NO tokens
* Prices reflect the market's implied probability of the outcome
