# Credit-card rewards and extra fees

Reviewed October 12, 2026. Scope: US fuel purchases.

`credit_cashback_percent` is a user estimate, default 0%, between 0 and 100.
Only card fuel purchases receive the reward. Cash receives none; an eligible
unknown-payment quote follows the user's selected cash/card assumption.
The raw quote, payment provenance, and pump purchase amount stay unchanged.

Estimated comparison cost = pump purchase − estimated card reward + detour fuel.
Time valuation is added separately for the balanced strategy. Rewards are not
applied to fuel already burned driving to the station. Break-even calculations
and uncertainty ranges use the same model. All-payment searches compare known
cash/card quotes using their net purchase price. Source freshness and verified
payment provenance still take precedence over an unverified quote.

The app does not verify card reward categories, merchant coding, caps, exclusions,
or redemption value. Enter the effective reward percentage that applies to you.
Rewards are shown separately from pump payment, as an estimate, not a pump discount.

## Cash/card price differences versus separate surcharges

Visa distinguishes a cash discount (posted card price, or both prices posted)
from an additional credit-card surcharge. The applicable US Visa surcharge limit
is the merchant's applicable acceptance cost or 3%, whichever is lower, with
disclosures at entry, checkout, and on the receipt. Visa debit/prepaid purchases
cannot be surcharged, even if processed through the terminal's credit option.

- [Visa US merchant surcharge Q&A](https://usa.visa.com/content/dam/VCOM/global/support-legal/documents/merchant-surcharging-qa-for-web.pdf)
- [Mastercard merchant surcharge rules](https://www.mastercard.com/us/en/business/support/merchant-surcharge-rules.html): cap 4%, subject to merchant acceptance costs and other brand/state requirements; debit/prepaid excluded.

California DOJ says merchants must not hide cash/card price differences or
misrepresent posted prices. Its SB 478 FAQ distinguishes an avoidable card fee
from a mandatory fee: a card-only business must include that fee in advertised
prices. Rules do not prove that a particular station charges a surcharge.

- [California DOJ: credit-card surcharges](https://oag.ca.gov/consumers/general/credit-card-surcharges)
- [California DOJ: SB 478 hidden fees FAQ](https://www.oag.ca.gov/hiddenfees)

Known card quotes already supply the card pump price: do not add a universal
cash/card difference again. The existing $0.20/gal user assumption is applied
only to quotes with unknown payment basis. It is not a verified surcharge.
Separate station-specific fees are not provided reliably by the current sources;
the app does not automatically add an unverified percentage or flat fee. Confirm
the pump disclosure and receipt. No specific station surcharge was live-verified
as part of this research.
