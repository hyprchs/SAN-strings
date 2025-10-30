import math
from functools import cache

import chess


def _sliding_delta(s1: chess.Square, s2: chess.Square) -> int:
    """
    Get the delta of the index in `chess.SQUARES` required to move
    one step from `s1` toward `s2`. Raises `AssertionError` if `s1`
    and `s2` are not on the same file, rank, or diagonal.

    >>> _sliding_delta(chess.C3, chess.F6)
    9
    >>> chess.C3 + 9 == chess.D4
    True
    """
    assert s1 != s2, 's1 and s2 must be different squares'

    x_delta = chess.square_file(s2) - chess.square_file(s1)
    y_delta = chess.square_rank(s2) - chess.square_rank(s1)

    assert 0 in (x_delta, y_delta) or abs(x_delta) == abs(y_delta), (
        's1 and s2 must be on the same file, rank, or diagonal; got '
        f'{chess.square_name(s1)} and {chess.square_name(s2)}'
    )

    x_delta = int(math.copysign(1, x_delta))
    y_delta = int(math.copysign(1, y_delta))

    return y_delta * 8 + x_delta


def extend_ray(
    from_sq: chess.Square,
    towards_sq: chess.Square,
) -> chess.Bitboard:
    """
    Get a `chess.Bitboard` of all the squares from (and including) `from_sq`
    toward `towards_sq` and continuing on to an edge of the board.

    >>> print(chess.SquareSet(extend_ray(chess.C3, chess.F6)))
    . . . . . . . 1
    . . . . . . 1 .
    . . . . . 1 . .
    . . . . 1 . . .
    . . . 1 . . . .
    . . 1 . . . . .
    . . . . . . . .
    . . . . . . . .
    """
    d = _sliding_delta(from_sq, towards_sq)
    # noinspection PyProtectedMember
    return chess._sliding_attacks(from_sq, 0, [d]) | chess.BB_SQUARES[from_sq]


def _assert_from_to_squares_different(move: chess.Move) -> None:
    if move.from_square == move.to_square:
        raise RuntimeError('Unexpected same-square move')


def is_diagonal_slide(move: chess.Move) -> bool:
    return abs(
        chess.square_file(move.from_square) - chess.square_file(move.to_square)
    ) == abs(chess.square_rank(move.from_square) - chess.square_rank(move.to_square))


def is_horizontal_or_vertical_slide(move: chess.Move) -> bool:
    return chess.square_file(move.from_square) == chess.square_file(
        move.to_square
    ) or chess.square_rank(move.from_square) == chess.square_rank(move.to_square)


@cache
def file_rank_deltas(move: chess.Move) -> tuple[int, int]:
    df = chess.square_file(move.from_square) - chess.square_file(move.to_square)
    dr = chess.square_rank(move.from_square) - chess.square_rank(move.to_square)
    return df, dr


def can_be_pawn_move(
    move: chess.Move,
    *,
    enforce_is_capture_as: bool | None = None,
    enforce_is_promotion_as: bool | None = None,
) -> bool:
    _assert_from_to_squares_different(move)
    df, dr = file_rank_deltas(move)
    abs_df = abs(df)
    abs_dr = abs(dr)

    # First filter out definitely-invalid pawn-like moves.
    # Can only go straight forward or left/right by 1 square
    if abs_df not in (0, 1):
        return False

    # Can only push pawns 1 or 2 squares
    if abs_dr not in (1, 2):
        return False

    # When moving 2 squares, need to check for correct from/to ranks
    if abs_dr == 2:
        # Double push can only go straight
        if df != 0:
            return False

        from_rank = chess.square_rank(move.from_square)
        to_rank = chess.square_rank(move.to_square)
        if dr == 2:
            # Must be white pawn move
            if (from_rank, to_rank) != (1, 3):
                return False
        elif dr == -2:
            # Must be black pawn move
            if (from_rank, to_rank) != (6, 4):
                return False
        else:
            raise RuntimeError('Bad logic above')

    # Require correct file delta if we only want captures or only non-captures
    if enforce_is_capture_as is not None:
        assert abs_df in (0, 1)
        if enforce_is_capture_as != (abs_df == 1):
            return False

    if enforce_is_promotion_as is not None:
        to_rank = chess.square_rank(move.to_square)
        if enforce_is_promotion_as != (to_rank in (0, 7)):
            return False

    return True


def can_be_knight_move(move: chess.Move) -> bool:
    _assert_from_to_squares_different(move)
    df, dr = file_rank_deltas(move)
    df = abs(df)
    dr = abs(dr)
    return (df == 1 and dr == 2) or (df == 2 and dr == 1)


def can_be_bishop_move(move: chess.Move) -> bool:
    _assert_from_to_squares_different(move)
    return is_diagonal_slide(move)


def can_be_rook_move(move: chess.Move) -> bool:
    _assert_from_to_squares_different(move)
    return is_horizontal_or_vertical_slide(move)


def can_be_queen_move(move: chess.Move) -> bool:
    _assert_from_to_squares_different(move)
    return is_diagonal_slide(move) or is_horizontal_or_vertical_slide(move)


def can_be_king_move(move: chess.Move) -> bool:
    _assert_from_to_squares_different(move)
    df, dr = file_rank_deltas(move)
    return max(abs(df), abs(dr)) == 1  # One square any direction (ignoring castling)
