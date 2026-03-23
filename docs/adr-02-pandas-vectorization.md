# ADR-02: Use Pandas Vectorization for Large Dataset Transformations

**Status:** Accepted  
**Date:** 2024-09-10  
**Author:** Data Engineering Guild

---

## Context

Several services perform row-by-row data transformations using Python `for` loops.
Profiling revealed this causes 10–100× overhead for datasets larger than 1 MB,
leading to request timeouts and worker saturation.

## Decision

Any data transformation operating on a dataset **greater than 1 MB** (or >10,000
rows) **MUST** use **Pandas vectorized operations** instead of Python-level loops.

### Rule of Thumb

| Dataset Size | Allowed Approach            |
|--------------|-----------------------------|
| < 1 MB       | Python loop or list compr.  |
| ≥ 1 MB       | Pandas vectorized ops       |
| > 1 GB       | Pandas + chunked I/O or Dask|

### Examples

```python
# ✅ Correct — vectorized
df["normalized"] = (df["value"] - df["value"].mean()) / df["value"].std()

# ❌ Incorrect for large data — slow Python loop
result = []
for val in data:
    result.append((val - mean) / std)
```

## Consequences

- **Positive:** Typical 20–50× speedup on 5 MB datasets (benchmarked 2024-Q3).
- **Positive:** Memory layout is cache-friendly; uses NumPy SIMD under the hood.
- **Negative:** Requires `pandas` in the service image (+20 MB); acceptable trade-off.

## References

- [Pandas Performance Tips](https://pandas.pydata.org/docs/user_guide/enhancingperf.html)
- Internal benchmark report: `docs/benchmarks/vectorization-report-Q3-2024.pdf`
