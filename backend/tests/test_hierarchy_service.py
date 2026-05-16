import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from app.services.hierarchy_service import HierarchyService


def _mock_hierarchy_result(rel):
    """Create a mock result row for an AgentHierarchy relation."""
    result = MagicMock()
    obj = MagicMock()
    obj.parent_agent_id = rel[0]
    obj.child_agent_id = rel[1]
    result.scalars.return_value.all.return_value = [obj]
    result.scalar_one_or_none.return_value = obj
    result.all.return_value = [(obj, MagicMock())]
    return result


def _mock_empty_result():
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    result.scalar_one_or_none.return_value = None
    result.all.return_value = []
    return result


@pytest.mark.asyncio
async def test_would_create_cycle():
    """Adding child->parent to an existing parent->child should be detected as a cycle."""
    service = HierarchyService()

    parent_id = uuid4()
    child_id = uuid4()

    db = AsyncMock()
    # _check_transitive(db, child_id, parent_id, max_depth=10)
    # 1st call: direct relation check (child_id -> parent_id) -> exists
    db.execute.return_value = _mock_hierarchy_result((child_id, parent_id))

    result = await service._would_create_cycle(db, parent_id, child_id)
    assert result is True


@pytest.mark.asyncio
async def test_no_cycle():
    """A simple parent->child should not create a cycle when adding child->grandchild."""
    service = HierarchyService()

    parent_id = uuid4()
    child_id = uuid4()
    grandchild_id = uuid4()

    db = AsyncMock()

    # _check_transitive(db, grandchild_id, child_id, max_depth=10)
    # Call 1: direct relation (grandchild -> child) -> None
    # Call 2: children of grandchild -> []
    # Call 3: children of child -> [parent_id -> child_id]
    # Call 4 (recurse on parent_id): direct relation (parent -> child) -> exists but != child_id
    #   Actually let me think again.
    #   We call _check_transitive(grandchild_id, child_id, 10).
    #   1. direct check: select where parent=grandchild_id, child=child_id -> None
    #   2. select where parent=grandchild_id -> [] (no children)
    #   return False
    # So only 2 calls needed.

    db.execute.side_effect = [
        _mock_empty_result(),   # direct check: grandchild -> child = no
        _mock_empty_result(),   # children of grandchild = []
    ]

    result = await service._would_create_cycle(db, child_id, grandchild_id)
    assert result is False


@pytest.mark.asyncio
async def test_would_create_cycle_indirect():
    """A->B->C exists; adding C->A should be detected as a cycle."""
    service = HierarchyService()

    a_id = uuid4()
    b_id = uuid4()
    c_id = uuid4()

    db = AsyncMock()

    # _check_transitive(db, c_id, a_id, max_depth=10)
    # Call 1: direct check (c -> a) -> None
    # Call 2: children of c -> [c->a? no. Hmm]
    # Wait: _check_transitive checks parent_agent_id = c_id.
    # The hierarchy has A->B, B->C. So:
    #   select where parent=c_id -> [] (C has no children)
    # So this returns False... unless we also check transitive through parents?
    # Let me re-read _check_transitive:
    #
    # async def _check_transitive(self, db, agent_id, target_id, max_depth, current_depth=0):
    #     if current_depth >= max_depth: return False
    #     result = db.execute(select(AgentHierarchy).where(parent_agent_id == agent_id))
    #     relations = result.scalars().all()
    #     for rel in relations:
    #         if rel.child_agent_id == target_id: return True
    #         if await self._check_transitive(db, rel.child_agent_id, target_id, max_depth, current_depth+1):
    #             return True
    #     return False
    #
    # So _check_transitive(c_id, a_id) checks: C's children -> none -> False.
    # But the hierarchy is A->B, B->C, and we want to add C->A.
    # The cycle check is: _would_create_cycle(db, a_id, c_id) = _check_transitive(db, c_id, a_id)
    # C has no children in the existing graph, so this returns False.
    # Wait, that's wrong. Let me re-check:
    #
    # _would_create_cycle(parent_id=a_id, child_id=c_id):
    #   checks if a_id is already a descendant of c_id
    #   i.e., _check_transitive(db, c_id, a_id)
    #
    # With A->B, B->C: does c_id have a path to a_id?
    # C's children: none (B->C means B is parent of C, C is child)
    # So C has no children. _check_transitive returns False.
    # But wait -- the cycle would be C->A->B->C, which means we need
    # to check if A is reachable from C going DOWN the tree.
    # Since A is ABOVE C, not below, there's no cycle from C's perspective.
    #
    # Hmm, actually the question is: if we add C->A (C is parent, A is child),
    # would there be a cycle? The existing path A->B->C means A can reach C.
    # Adding C->A means C can reach A. So there IS a cycle: A->B->C->A.
    #
    # But _would_create_cycle checks if a_id (the new parent) is already a
    # descendant of c_id (the new child). It traverses DOWN from c_id.
    # Since c_id has no children, it returns False. That seems wrong!
    #
    # Wait, I misread. Let me re-read:
    # _would_create_cycle(self, db, parent_id, child_id):
    #   return await self._check_transitive(db, child_id, parent_id, max_depth=10)
    #
    # So for adding C->A: parent=c_id, child=a_id
    # _check_transitive(db, a_id, c_id)
    # This checks: starting from a_id, can we reach c_id by following children?
    # A's children: [B] (A->B)
    # B.child_agent_id == c_id? Let's check: B->C means parent=B, child=C
    # So rel.child_agent_id = c_id -> match! Return True.
    #
    # So the cycle IS detected. But I need to set up the mocks correctly.
    # For _would_create_cycle(db, c_id, a_id):
    #   _check_transitive(db, a_id, c_id)
    #   1. direct check: select where parent=a_id, child=c_id -> None (A->C doesn't exist directly)
    #   2. children of a_id -> [relation with child=b_id]
    #   3. check rel.child_agent_id == c_id? b_id != c_id, so recurse
    #   4. _check_transitive(db, b_id, c_id)
    #      4a. direct check: select where parent=b_id, child=c_id -> exists (B->C)
    #      4b. return True

    rel_a_b = MagicMock()
    rel_a_b.child_agent_id = b_id

    rel_b_c = MagicMock()
    rel_b_c.child_agent_id = c_id

    # Mock calls in order:
    # 1. _check_transitive(a_id, c_id): direct check (a -> c) -> None
    # 2. children of a_id -> [rel_a_b]
    # 3. recurse _check_transitive(b_id, c_id): direct check (b -> c) -> rel_b_c
    direct_none = MagicMock()
    direct_none.scalar_one_or_none.return_value = None

    children_of_a = MagicMock()
    children_of_a.scalars.return_value.all.return_value = [rel_a_b]

    direct_b_c = MagicMock()
    direct_b_c.scalar_one_or_none.return_value = rel_b_c

    db.execute.side_effect = [direct_none, children_of_a, direct_b_c]

    result = await service._would_create_cycle(db, c_id, a_id)
    assert result is True


@pytest.mark.asyncio
async def test_no_cycle_simple_parent_child():
    """Adding A->B when no existing relations should not create a cycle."""
    service = HierarchyService()

    a_id = uuid4()
    b_id = uuid4()

    db = AsyncMock()
    # _check_transitive(db, b_id, a_id, 10)
    # 1. direct check (b -> a) -> None
    # 2. children of b -> []
    db.execute.side_effect = [_mock_empty_result(), _mock_empty_result()]

    result = await service._would_create_cycle(db, a_id, b_id)
    assert result is False
