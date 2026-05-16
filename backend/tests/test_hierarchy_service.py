import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from app.services.hierarchy_service import HierarchyService


def _make_relation(parent_id, child_id):
    """Create a mock AgentHierarchy relation object."""
    rel = MagicMock()
    rel.parent_agent_id = parent_id
    rel.child_agent_id = child_id
    return rel


def _mock_execute_result(relations):
    """Create a mock db.execute result that returns the given relations via scalars().all()."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = relations
    return result


@pytest.mark.asyncio
async def test_would_create_cycle():
    """Adding child->parent to an existing parent->child should be detected as a cycle.

    Existing: parent -> child
    Proposed: child -> parent (i.e. _would_create_cycle(db, child, parent))
    _check_transitive(db, parent, child):
        query children of parent -> [rel(parent->child)]
        rel.child_agent_id == child -> True!
    """
    service = HierarchyService()
    parent_id = uuid4()
    child_id = uuid4()

    db = AsyncMock()
    rel = _make_relation(parent_id, child_id)
    db.execute = AsyncMock(return_value=_mock_execute_result([rel]))

    # _would_create_cycle(db, parent=child_id, child=parent_id)
    # means: would adding child_id->parent_id create a cycle?
    # _check_transitive(db, parent_id, child_id): query children of parent_id
    # finds rel(parent->child), child_agent_id == child_id -> True
    result = await service._would_create_cycle(db, child_id, parent_id)
    assert result is True


@pytest.mark.asyncio
async def test_no_cycle():
    """A simple parent->child should not create a cycle when adding child->grandchild.

    Existing: parent -> child
    Proposed: child -> grandchild
    _check_transitive(db, grandchild, child):
        query children of grandchild -> [] (no children)
        return False
    """
    service = HierarchyService()
    parent_id = uuid4()
    child_id = uuid4()
    grandchild_id = uuid4()

    db = AsyncMock()
    # No children of grandchild_id
    db.execute = AsyncMock(return_value=_mock_execute_result([]))

    result = await service._would_create_cycle(db, child_id, grandchild_id)
    assert result is False


@pytest.mark.asyncio
async def test_would_create_cycle_indirect():
    """A->B->C exists; adding C->A should be detected as a cycle.

    Existing: A->B, B->C
    Proposed: C->A (i.e. _would_create_cycle(db, C, A))
    _check_transitive(db, A, C):
        query children of A -> [rel(A->B)]
        rel.child_agent_id = B != C -> recurse _check_transitive(B, C)
            query children of B -> [rel(B->C)]
            rel.child_agent_id = C == C -> True!
    """
    service = HierarchyService()
    a_id = uuid4()
    b_id = uuid4()
    c_id = uuid4()

    db = AsyncMock()
    rel_a_b = _make_relation(a_id, b_id)
    rel_b_c = _make_relation(b_id, c_id)

    # Two sequential db.execute calls:
    # 1. query children of a_id -> [rel_a_b]
    # 2. query children of b_id -> [rel_b_c]
    db.execute = AsyncMock(side_effect=[
        _mock_execute_result([rel_a_b]),
        _mock_execute_result([rel_b_c]),
    ])

    result = await service._would_create_cycle(db, c_id, a_id)
    assert result is True


@pytest.mark.asyncio
async def test_no_cycle_simple_parent_child():
    """Adding A->B when no existing relations should not create a cycle.

    _check_transitive(db, B, A):
        query children of B -> [] (no relations)
        return False
    """
    service = HierarchyService()
    a_id = uuid4()
    b_id = uuid4()

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_mock_execute_result([]))

    result = await service._would_create_cycle(db, a_id, b_id)
    assert result is False
