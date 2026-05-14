"""Unit tests for jobs/spatial.py"""

import pandas as pd
import pytest
from shapely.geometry import Point

from jobs.spatial import (
    aggregate_by_building,
    build_geodataframe,
    build_insight_rows,
)


def _anomalies() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "job_id": ["j1", "j1", "j1", "j1"],
            "room_id": ["conference-a1", "conference-a1", "conference-b2", "server-room-e5"],
            "anomaly_type": ["temperature", "temperature", "unusual_activity", "temperature"],
            "severity": ["high", "medium", "medium", "high"],
            "detected_at": pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]),
        }
    )


def _rooms() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "room_id": ["conference-a1", "conference-b2", "server-room-e5"],
            "building_id": ["building-a", "building-b", "building-e"],
            "building_name": ["Building A", "Building B", "Building E"],
            "lat": [51.2195, 51.2201, 51.2189],
            "lon": [4.4024, 4.4038, 4.4015],
        }
    )


# ──────────────────────────────────────────────────────────────────────────────
# build_geodataframe
# ──────────────────────────────────────────────────────────────────────────────


class TestBuildGeoDataFrame:
    def test_returns_geodataframe(self) -> None:
        import geopandas as gpd

        gdf = build_geodataframe(_anomalies(), _rooms())
        assert isinstance(gdf, gpd.GeoDataFrame)

    def test_crs_is_wgs84(self) -> None:
        gdf = build_geodataframe(_anomalies(), _rooms())
        assert gdf.crs.to_epsg() == 4326

    def test_geometry_is_point(self) -> None:
        gdf = build_geodataframe(_anomalies(), _rooms())
        assert all(isinstance(g, Point) for g in gdf.geometry)

    def test_joins_on_room_id(self) -> None:
        gdf = build_geodataframe(_anomalies(), _rooms())
        assert "building_id" in gdf.columns
        assert len(gdf) == len(_anomalies())

    def test_drops_anomalies_without_room(self) -> None:
        anomalies = _anomalies().copy()
        anomalies.loc[0, "room_id"] = "unknown-room"
        gdf = build_geodataframe(anomalies, _rooms())
        assert len(gdf) == 3


# ──────────────────────────────────────────────────────────────────────────────
# aggregate_by_building
# ──────────────────────────────────────────────────────────────────────────────


class TestAggregateByBuilding:
    def setup_method(self) -> None:
        self.gdf = build_geodataframe(_anomalies(), _rooms())

    def test_one_row_per_building(self) -> None:
        agg = aggregate_by_building(self.gdf)
        assert len(agg) == 3

    def test_anomaly_count_correct(self) -> None:
        agg = aggregate_by_building(self.gdf)
        building_a = agg[agg["building_id"] == "building-a"].iloc[0]
        assert building_a["anomaly_count"] == 2

    def test_high_count_correct(self) -> None:
        agg = aggregate_by_building(self.gdf)
        building_a = agg[agg["building_id"] == "building-a"].iloc[0]
        assert building_a["high_count"] == 1
        assert building_a["medium_count"] == 1

    def test_dominant_type_is_most_frequent(self) -> None:
        agg = aggregate_by_building(self.gdf)
        building_a = agg[agg["building_id"] == "building-a"].iloc[0]
        assert building_a["dominant_type"] == "temperature"

    def test_coordinates_preserved(self) -> None:
        agg = aggregate_by_building(self.gdf)
        building_a = agg[agg["building_id"] == "building-a"].iloc[0]
        assert building_a["lat"] == pytest.approx(51.2195)
        assert building_a["lon"] == pytest.approx(4.4024)


# ──────────────────────────────────────────────────────────────────────────────
# build_insight_rows
# ──────────────────────────────────────────────────────────────────────────────


class TestBuildInsightRows:
    def setup_method(self) -> None:
        gdf = build_geodataframe(_anomalies(), _rooms())
        self.agg = aggregate_by_building(gdf)
        self.period_start = pd.Timestamp("2026-01-05")
        self.period_end = pd.Timestamp("2026-01-08")

    def test_returns_one_row_per_building(self) -> None:
        rows = build_insight_rows(self.agg, "job-1", self.period_start, self.period_end)
        assert len(rows) == 3

    def test_row_contains_required_keys(self) -> None:
        rows = build_insight_rows(self.agg, "job-1", self.period_start, self.period_end)
        required = {
            "job_id",
            "building_id",
            "building_name",
            "lat",
            "lon",
            "anomaly_count",
            "high_count",
            "medium_count",
            "dominant_type",
            "period_start",
            "period_end",
        }
        assert required.issubset(rows[0].keys())

    def test_job_id_set_correctly(self) -> None:
        rows = build_insight_rows(self.agg, "job-42", self.period_start, self.period_end)
        assert all(r["job_id"] == "job-42" for r in rows)

    def test_anomaly_count_is_int(self) -> None:
        rows = build_insight_rows(self.agg, "job-1", self.period_start, self.period_end)
        assert all(isinstance(r["anomaly_count"], int) for r in rows)
