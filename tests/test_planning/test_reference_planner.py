"""Tests for planning.reference_planner."""
from lfo.planning.reference_planner import R2V_SLOT_COUNT, plan_references
from lfo.storyboard.storyboard import (
    CharacterAppearance,
    ContinuityChain,
    ProjectInfo,
    Shot,
    Storyboard,
)


class TestPlanReferences:
    def _make_storyboard(self, shots=None, chains=None, project=None):
        return Storyboard(
            project=project or ProjectInfo(project_id="proj_001"),
            shots=shots or [],
            continuity_chains=chains or [],
        )

    def test_empty_shot(self):
        """Shot with no characters/scene returns empty or minimal refs."""
        sb = self._make_storyboard(shots=[Shot(shot_id="shot_001")])
        refs = plan_references(sb.shots[0], sb)
        # No characters, no scene → only composition
        assert len(refs) <= 1

    def test_max_3_slots(self):
        """Never returns more than 3 references."""
        sb = self._make_storyboard(
            shots=[
                Shot(
                    shot_id="shot_001",
                    scene_id="scene_001",
                    characters=[
                        CharacterAppearance(character_id="char_001"),
                        CharacterAppearance(character_id="char_002"),
                    ],
                ),
            ],
        )
        refs = plan_references(sb.shots[0], sb)
        assert len(refs) <= R2V_SLOT_COUNT

    def test_3_plus_characters_ineligible(self):
        """3+ identity characters → R2V ineligible (empty list)."""
        sb = self._make_storyboard(
            shots=[
                Shot(
                    shot_id="shot_001",
                    characters=[
                        CharacterAppearance(character_id="char_001"),
                        CharacterAppearance(character_id="char_002"),
                        CharacterAppearance(character_id="char_003"),
                    ],
                ),
            ],
        )
        refs = plan_references(sb.shots[0], sb)
        assert refs == []

    def test_two_characters_plus_composition(self):
        """2 characters + composition fills 3 slots."""
        sb = self._make_storyboard(
            shots=[
                Shot(
                    shot_id="shot_001",
                    scene_id="scene_001",
                    characters=[
                        CharacterAppearance(character_id="char_001"),
                        CharacterAppearance(character_id="char_002"),
                    ],
                ),
            ],
        )
        refs = plan_references(sb.shots[0], sb)
        # Should have: char_001, char_002, composition (or scene)
        assert len(refs) == 3
        roles = [r.role for r in refs]
        assert roles.count("character") == 2

    def test_slot_ordering(self):
        """Slots should be numbered 1, 2, 3 sequentially."""
        sb = self._make_storyboard(
            shots=[
                Shot(
                    shot_id="shot_001",
                    scene_id="scene_001",
                    characters=[CharacterAppearance(character_id="char_001")],
                ),
            ],
        )
        refs = plan_references(sb.shots[0], sb)
        slots = [r.slot for r in refs]
        assert slots == list(range(1, len(refs) + 1))

    def test_character_priority_over_composition(self):
        """Characters should get lower slot numbers than composition."""
        sb = self._make_storyboard(
            shots=[
                Shot(
                    shot_id="shot_001",
                    scene_id="scene_001",
                    characters=[CharacterAppearance(character_id="char_001")],
                ),
            ],
        )
        refs = plan_references(sb.shots[0], sb)
        char_refs = [r for r in refs if r.role == "character"]
        comp_refs = [r for r in refs if r.role == "composition"]
        if char_refs and comp_refs:
            assert char_refs[0].slot < comp_refs[0].slot

    def test_chain_character_order(self):
        """Character order from continuity chain is respected."""
        sb = self._make_storyboard(
            shots=[
                Shot(
                    shot_id="shot_001",
                    characters=[
                        CharacterAppearance(character_id="char_A"),
                        CharacterAppearance(character_id="char_B"),
                    ],
                ),
            ],
            chains=[
                ContinuityChain(
                    chain_id="chain_1",
                    shot_ids=["shot_001"],
                    reference_character_order=["char_B", "char_A"],
                ),
            ],
        )
        refs = plan_references(sb.shots[0], sb)
        char_refs = [r for r in refs if r.role == "character"]
        if len(char_refs) == 2:
            # char_B should come before char_A per chain order
            assert char_refs[0].entity_id == "char_B"
            assert char_refs[1].entity_id == "char_A"

    def test_project_character_order(self):
        """Project-level character order is used when no chain order."""
        sb = self._make_storyboard(
            shots=[
                Shot(
                    shot_id="shot_001",
                    characters=[
                        CharacterAppearance(character_id="char_X"),
                        CharacterAppearance(character_id="char_Y"),
                    ],
                ),
            ],
            project=ProjectInfo(
                project_id="proj_001",
                reference_character_order=["char_Y", "char_X"],
            ),
        )
        refs = plan_references(sb.shots[0], sb)
        char_refs = [r for r in refs if r.role == "character"]
        if len(char_refs) == 2:
            assert char_refs[0].entity_id == "char_Y"

    def test_symbolic_when_no_asset(self):
        """References should be symbolic when no approved asset available."""
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001", scene_id="scene_001")],
        )
        refs = plan_references(sb.shots[0], sb, available_assets={})
        for r in refs:
            assert r.is_symbolic is True
            assert r.asset_id.startswith("SYMBOLIC_")

    def test_resolved_when_asset_available(self):
        """References should not be symbolic when approved asset exists."""
        sb = self._make_storyboard(
            shots=[
                Shot(
                    shot_id="shot_001",
                    characters=[CharacterAppearance(character_id="char_001")],
                ),
            ],
        )
        assets = {
            "char_001": {
                "character_ref": {"status": "approved", "asset_id": "asset_char_001_ref"},
            },
        }
        refs = plan_references(sb.shots[0], sb, available_assets=assets)
        char_refs = [r for r in refs if r.role == "character"]
        if char_refs:
            assert char_refs[0].is_symbolic is False
            assert char_refs[0].asset_id == "asset_char_001_ref"

    def test_dedup_by_asset_id(self):
        """Same asset_id for different roles should be deduped."""
        sb = self._make_storyboard(
            shots=[
                Shot(
                    shot_id="shot_001",
                    scene_id="scene_001",
                    characters=[CharacterAppearance(character_id="char_001")],
                ),
            ],
        )
        # Both character and composition resolve to same asset
        assets = {
            "char_001": {
                "character_ref": {"status": "approved", "asset_id": "same_asset"},
            },
            "shot_001": {
                "composition_ref": {"status": "approved", "asset_id": "same_asset"},
            },
        }
        refs = plan_references(sb.shots[0], sb, available_assets=assets)
        asset_ids = [r.asset_id for r in refs]
        assert len(asset_ids) == len(set(asset_ids))

    def test_determinism(self):
        """Same inputs → same reference bindings."""
        sb = self._make_storyboard(
            shots=[
                Shot(
                    shot_id="shot_001",
                    scene_id="scene_001",
                    characters=[CharacterAppearance(character_id="char_001")],
                ),
            ],
        )
        r1 = plan_references(sb.shots[0], sb)
        r2 = plan_references(sb.shots[0], sb)
        assert len(r1) == len(r2)
        for a, b in zip(r1, r2):
            assert a.slot == b.slot
            assert a.asset_id == b.asset_id
            assert a.entity_id == b.entity_id
            assert a.role == b.role
