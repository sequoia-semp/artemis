# Strip Conventions

Power strips are weighted by reference hours.

```text
strip_price = sum(month_price_i * reference_hours_i) / sum(reference_hours_i)
value = MW * sum(reference_hours_i * price_i)
```

Gas strips are weighted by delivery days under the v0.1 `.25/d` contract-equivalent convention.

```text
total_MMBtu = contracts * 2500 * delivery_days
value = total_MMBtu * price
```
