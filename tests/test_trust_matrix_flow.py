# tests/test_trust_matrix_flow.py
import pytest

def init_trust_matrix(player_ids):
    """初始化N×N信任矩阵，默认值为50（中立）"""
    return {pid: {other_pid: 50 for other_pid in player_ids} for pid in player_ids}

def update_trust_matrix(matrix, from_pid, to_pid, delta):
    """更新信任矩阵，delta为变化值（正=信任增加，负=信任降低）"""
    matrix[from_pid][to_pid] = max(0, min(100, matrix[from_pid][to_pid] + delta))
    return matrix

def test_matrix_initialization():
    """测试信任矩阵初始化正确"""
    players = [1,2,3,4,5,6]
    matrix = init_trust_matrix(players)
    assert len(matrix) == len(players), "矩阵行数与玩家数不符"
    for pid in players:
        assert all(matrix[pid][other] == 50 for other in players), "初始信任值不为中立"

def test_matrix_dynamic_update():
    """测试信任矩阵能正确动态更新"""
    players = [1,2,3,4,5,6]
    matrix = init_trust_matrix(players)
    # 玩家1发言后，玩家2对玩家1的信任值降低20
    updated_matrix = update_trust_matrix(matrix, from_pid=2, to_pid=1, delta=-20)
    assert updated_matrix[2][1] == 30, "信任值未正确更新"

def test_matrix_bounds():
    """测试信任值不会超出0-100的范围"""
    players = [1,2]
    matrix = init_trust_matrix(players)
    matrix = update_trust_matrix(matrix, from_pid=1, to_pid=2, delta=100)
    assert matrix[1][2] == 100, "信任值超出上限"
    matrix = update_trust_matrix(matrix, from_pid=1, to_pid=2, delta=-150)
    assert matrix[1][2] == 0, "信任值低于下限"