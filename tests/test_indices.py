from pga_workbench.indices import normalize_power_index, normalize_gas_index


def test_bare_power_defaults_to_rt_full_lmp_atc():
    idx = normalize_power_index("WH")
    assert idx.commodity == "power"
    assert idx.market_run == "RT"
    assert idx.price_component == "FULL_LMP"
    assert idx.shape == "ATC"
    assert idx.is_defaulted is True


def test_power_explicit_da_peak():
    idx = normalize_power_index("WH DA Peak")
    assert idx.market_run == "DA"
    assert idx.shape == "PEAK"
    assert idx.price_component == "FULL_LMP"


def test_gas_defaults_to_gdd():
    idx = normalize_gas_index("TETCO-M3")
    assert idx.location_id == "TETCO_M3"
    assert idx.index_family == "GDD"
    assert idx.is_defaulted is True


def test_gas_explicit_iferc_override():
    idx = normalize_gas_index("TETCO-M3 IFERC")
    assert idx.location_id == "TETCO_M3"
    assert idx.index_family == "IFERC"
    assert idx.is_defaulted is False


def test_gas_hh_ld1():
    idx = normalize_gas_index("HH LD1")
    assert idx.location_id == "HH"
    assert idx.index_family == "LD1"
