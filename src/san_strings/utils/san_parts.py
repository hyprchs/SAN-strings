from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from copy import deepcopy
from functools import reduce
from operator import or_
from typing import Iterable

import chess

from san_strings.constants import (
    CORNER_SQUARES,
    EDGE_SQUARES,
    NON_PAWN_SAN_REGEX,
    PAWN_SAN_REGEX,
)
from san_strings.utils import (
    attacked_by_mask,
    extend_ray,
    is_diagonal_slider,
    is_orthogonal_slider,
    is_slider,
    ordinal,
)


class SanParts(ABC):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()
        if not hasattr(cls, 'from_san'):
            raise TypeError(
                f'Class {cls.__name__} must define `from_san()` classmethod'
            )

    def __init__(
        self,
        *,
        piece_type: chess.PieceType,
        is_capture: bool = False,
        to_square: chess.Square,
        check_or_mate: str | None = None,
    ):
        self.piece_type = piece_type
        self.is_capture = is_capture
        self.to_square = to_square
        self.check_or_mate = check_or_mate

    @property
    def check_or_mate(self):
        return self._check_or_mate

    @check_or_mate.setter
    def check_or_mate(self, value: str | None):
        if value not in ('+', '#', None):
            raise ValueError('Invalid `check_or_mate` value')
        self._check_or_mate = value

    @property
    @abstractmethod
    def rendered(self) -> str: ...

    @property
    @abstractmethod
    def iter_positions(
        self,
        *,
        place_kings: bool = True,
    ) -> Iterable[tuple[chess.Board, chess.Move]]:
        """
        Iterate over positions with only the moving piece type and kings that can cause the given SAN,
        considering any disambiguators. Expects valid non-check/mate SANs.

        TODO: Support check/mate here to prove check/mate SANs.
        """
        ...

    @property
    @abstractmethod
    def can_cause_discovered_attack(self):
        """
        Return `True` iff the move can cause a discovered attack.

        Key concept for this method:
          - Pieces can only cause discovered attacks by revealing an attack from another slider
            that slides in a direction the moving piece does not.

        Corollaries:
          - Bishops move diagonally, so they cannot reveal discovered attacks by diagonal sliders.
          - Rooks move orthogonally, so they cannot reveal discovered attacks by orthogonal sliders.
          - Queens move diagonally + orthogonally, so they cannot reveal any discovered attacks in any direction.

        Further: board geometry means that the attacking piece would need to be off the board when diagonal slider
        moves start on a corner or orthogonal slider moves start on an edge, so these are also true:
          - Bishops can cause discovered attacks iff their `from_square` is not in a corner.
          - Rooks can cause discovered attacks iff their `from_square` is not on an edge.

        And more generally (ex. this applies to knights):
          - Any move starting in a corner can never cause discovered attack as there are no squares "behind" the
            `from_square` diagonally or orthogonally.

        Important: We don't know the exact `from_square` from the SAN we have available here. Rather, the SAN
        determines a set of possible board (board configuration) that would require  the observed SAN
        (including any disambiguations).

        Therefore, the goal for subclasses is to determine whether *any* of those positions have a `from_square`
        that is *not* in a corner for bishop moves or that is *not* on an edge for rook moves.

        In some cases we can show with brute force that all moves + piece configurations where the SAN occurs
        start in a corner/edge respectively, meaning discovered attacks are impossible.
        """
        ...

    @property
    @abstractmethod
    def moving_piece_can_cause_check(self):
        """
        Return `True` iff the moving piece can directly cause new squares to be attacked on the board
        (not via discoveries).
        """
        ...

    @property
    def can_cause_check(self):
        """
        Return `True` iff the move can cause check either directly by attacking new squares or with a discovery.
        """
        return self.can_cause_discovered_attack or self.moving_piece_can_cause_check

    @classmethod
    def from_san(cls, san: str) -> SanParts:
        try:
            return NBRQSanParts.from_san(san)
        except ValueError:
            pass
        try:
            return PawnSanParts.from_san(san)
        except ValueError:
            pass
        try:
            return KingSanParts.from_san(san)
        except ValueError:
            pass
        raise ValueError(f'Could not parse SAN: {san}')

    def __str__(self) -> str:
        return f'{self.__class__.__name__}({self.rendered})'

    def copy(self):
        return deepcopy(self)


class PawnSanParts(SanParts):
    def __init__(
        self,
        *,
        file_disambiguator: int | None = None,
        is_capture: bool = False,
        to_square: chess.Square,
        check_or_mate: str | None = None,
        promotion_piece_type: chess.PieceType | None = None,
    ):
        # Validation
        if (file_disambiguator is not None) != is_capture:
            raise ValueError(
                'Must specify `file_disambiguator` iff `is_capture` is `True`'
            )
        if (
            file_disambiguator is not None
            and abs(
                chess.square_file(file_disambiguator) - chess.square_file(to_square)
            )
            != 1
        ):
            raise ValueError(
                f'Expected `file_disambiguator` to be on an adjacent file to `to_square` {chess.square_name(to_square)}'
            )
        if (promotion_piece_type is not None) != (
            chess.square_rank(to_square) in (0, 7)
        ):
            raise ValueError(
                'Must specify `promotion_piece_type` if `to_square` is on a back rank'
            )
        super().__init__(
            piece_type=chess.PAWN,
            is_capture=is_capture,
            to_square=to_square,
            check_or_mate=check_or_mate,
        )
        self.file_disambiguator = file_disambiguator
        self.promotion_piece_type = promotion_piece_type

    @property
    def rendered(self) -> str:
        return (
            f'{f"{chess.FILE_NAMES[self.file_disambiguator]}x" if self.file_disambiguator is not None else ""}'
            f'{chess.square_name(self.to_square)}'
            f'{f"={chess.piece_symbol(self.promotion_piece_type).upper()}" if self.promotion_piece_type is not None else ""}'
            f'{self.check_or_mate if self.check_or_mate is not None else ""}'
        )

    @property
    def iter_positions(
        self,
        *,
        place_kings: bool = True,
    ) -> Iterable[tuple[chess.Board, chess.Move]]:
        if self.check_or_mate is not None:
            raise RuntimeError(
                'This method does not yet support calling when `check_or_mate` is set'
            )

        b = chess.Board.empty()

        # Manually get squares where pawn could have come from.
        to_rank = chess.square_rank(self.to_square)
        to_rank_to_w_candidate_from_ranks_map = {
            0: [],
            1: [],
            2: [1],
            3: [2],
            4: [3],
            5: [4],
            6: [5],
            7: [6],
        }
        to_rank_to_b_candidate_from_ranks_map = {
            0: [1],
            1: [2],
            2: [3],
            3: [4],
            4: [5],
            5: [6],
            6: [],
            7: [],
        }
        if self.is_capture:
            if self.file_disambiguator is None:
                raise RuntimeError('Internal error: bad state')
            from_file = self.file_disambiguator
        else:
            from_file = chess.square_file(self.to_square)
            # Non-captures: add possibilities for double moves
            to_rank_to_w_candidate_from_ranks_map[3].append(1)  # 2nd rank
            to_rank_to_b_candidate_from_ranks_map[4].append(6)  # 7th rank

        # Rank masks
        w_candidate_from_ranks_mask = reduce(
            or_,
            (chess.BB_RANKS[r] for r in to_rank_to_w_candidate_from_ranks_map[to_rank]),
            chess.BB_EMPTY,
        )
        b_candidate_from_ranks_mask = reduce(
            or_,
            (chess.BB_RANKS[r] for r in to_rank_to_b_candidate_from_ranks_map[to_rank]),
            chess.BB_EMPTY,
        )

        # Square masks using correct `from_file`
        w_candidate_from_squares_mask = (
            chess.BB_FILES[from_file] & w_candidate_from_ranks_mask
        )
        b_candidate_from_squares_mask = (
            chess.BB_FILES[from_file] & b_candidate_from_ranks_mask
        )

        # Here we need to be sure we are placing a pawn of the right color.
        for color, candidate_from_squares_mask in (
            (chess.WHITE, w_candidate_from_squares_mask),
            (chess.BLACK, b_candidate_from_squares_mask),
        ):
            b.turn = color
            candidate_from_squares = chess.SquareSet(candidate_from_squares_mask)
            for from_square in candidate_from_squares:
                move = chess.Move(
                    from_square,
                    self.to_square,
                    promotion=self.promotion_piece_type,
                )
                b_new = b.copy()
                b_new.set_piece_at(from_square, chess.Piece(self.piece_type, color))

                # For captures, set a black piece at `to_square`.
                if self.is_capture:
                    b_new.set_piece_at(
                        self.to_square, chess.Piece(chess.KNIGHT, not color)
                    )

                actual_san = b_new.san(move)
                if actual_san != self.rendered:
                    raise RuntimeError(
                        f'Internal error: actual SAN does not match expected:\n'
                        f'actual:   {actual_san}\n'
                        f'expected: {self.rendered}'
                    )
                yield b_new, move

    @property
    def can_cause_discovered_attack(self):
        if self.is_capture:
            # Pawn captures move 1 square diagonally, meaning they behave like a diagonal slider
            # in that they can cause discovered attacks when their `from_square` is not a corner.
            # This early return works because pawns cannot be on the 1st rank in standard chess
            # and will be promoted (becoming a non-pawn) upon reaching the 8th rank.
            # This means a pawn's `from_square` can never be any corner.
            return True

        # Non-capture pawn moves behave like orthogonal sliders in that they can cause discovered attacks
        # if their `from_square` is not an edge. Again, pawns cannot exist on either back rank,
        # so the question is whether the pawn starts on either the A or H file.
        # The `from_square` will always be on the same file as the `to_square`, so we can use it to check.
        return chess.square_file(self.to_square) not in (0, 7)

    @property
    def moving_piece_can_cause_check(self):
        # Pawns always cause new squares to be attacked. This is trivially true for non-promotions
        # and true for promotions because the promoted piece must attack new squares.
        return True

    @classmethod
    def from_san(cls, san: str) -> PawnSanParts:
        m = PAWN_SAN_REGEX.match(san)
        if m is None:
            raise ValueError(f'Invalid pawn move SAN: {san}')
        file_disambiguator = m.group('file_disambiguator')
        capture = m.group('capture')
        to_square = m.group('to_square')
        promotion = m.group('promotion')
        check_or_mate = m.group('check_or_mate')
        try:
            file_disambiguator = (
                chess.FILE_NAMES.index(file_disambiguator)
                if file_disambiguator is not None
                else None
            )
            is_capture = capture == 'x'
            to_square = chess.parse_square(to_square)
            promotion_piece_type = (
                chess.Piece.from_symbol(promotion).piece_type if promotion else None
            )
        except ValueError as e:
            raise ValueError(f'Failed to parse SAN: {san}') from e
        return cls(
            file_disambiguator=file_disambiguator,
            is_capture=is_capture,
            to_square=to_square,
            promotion_piece_type=promotion_piece_type,
            check_or_mate=check_or_mate,
        )


class NBRQSanParts(SanParts):
    def __init__(
        self,
        *,
        piece_type: chess.PieceType,
        file_disambiguator: int | None = None,
        rank_disambiguator: int | None = None,
        is_capture: bool = False,
        to_square: chess.Square,
        check_or_mate: str | None = None,
    ):
        if piece_type not in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
            raise ValueError(
                'Invalid `piece_type`, must be knight, bishop, rook, or queen'
            )
        if file_disambiguator is not None and not (0 <= file_disambiguator <= 7):
            raise ValueError('Invalid `file_disambiguator`')
        if rank_disambiguator is not None and not (0 <= rank_disambiguator <= 7):
            raise ValueError('Invalid `rank_disambiguator`')
        super().__init__(
            piece_type=piece_type,
            is_capture=is_capture,
            to_square=to_square,
            check_or_mate=check_or_mate,
        )
        self.file_disambiguator = file_disambiguator
        self.rank_disambiguator = rank_disambiguator

    @property
    def rendered(self) -> str:
        return (
            f'{chess.piece_symbol(self.piece_type).upper()}'
            f'{chess.FILE_NAMES[self.file_disambiguator] if self.file_disambiguator is not None else ""}'
            f'{chess.RANK_NAMES[self.rank_disambiguator] if self.rank_disambiguator is not None else ""}'
            f'{"x" if self.is_capture else ""}'
            f'{chess.square_name(self.to_square)}'
            f'{self.check_or_mate if self.check_or_mate is not None else ""}'
        )

    @property
    def iter_positions(
        self,
        *,
        place_kings: bool = True,
    ) -> Iterable[tuple[chess.Board, chess.Move]]:
        if self.check_or_mate is not None:
            raise RuntimeError(
                'This method does not yet support calling when `check_or_mate` is set'
            )

        b = chess.Board.empty()

        # Get pieces to place later.
        white_piece = chess.Piece(self.piece_type, chess.WHITE)

        # Put a piece on `to_square` and get the attacks bitboard.
        b.set_piece_at(self.to_square, white_piece)
        to_square_attacks_mask = b.attacks_mask(self.to_square)
        b.remove_piece_at(self.to_square)

        match self.file_disambiguator, self.rank_disambiguator:
            case int(from_file), int(from_rank):
                # Full-square disambiguator.

                # Get the `from_square` (the full-square disambiguator)
                file_name = chess.FILE_NAMES[from_file]
                rank_name = chess.RANK_NAMES[from_rank]
                from_square_name = f'{file_name}{rank_name}'
                assert from_square_name in chess.SQUARE_NAMES
                from_square = chess.parse_square(from_square_name)
                move = chess.Move(from_square, self.to_square)

                # Make sure the `from_square` attacks the `to_square`, otherwise this was an invalid SAN.
                if not to_square_attacks_mask & chess.BB_SQUARES[from_square]:
                    raise ValueError(
                        f'Full-square disambiguated SAN {self.rendered} is impossible because a '
                        f'{chess.piece_name(self.piece_type)} at full-square disambiguator '
                        f'{chess.square_name(from_square)} does not attack `to_square` '
                        f'{chess.square_name(self.to_square)}'
                    )

                # These will be all candidate corners for the other two pieces (excluding the `from_square`).
                candidate_rect_corners = chess.SquareSet(
                    to_square_attacks_mask & ~chess.BB_SQUARES[from_square]
                )
                if is_slider(self.piece_type):
                    candidate_rect_corners &= ~extend_ray(self.to_square, from_square)

                # Make sure we have candidates on the `from_file` and `from_rank` (otherwise SAN was invalid).
                if not (
                    candidate_rect_corners & chess.BB_FILES[from_file]
                    and candidate_rect_corners & chess.BB_RANKS[from_rank]
                ):
                    raise ValueError(
                        f'Full-square-disambiguated SAN {self.rendered} is impossible because simultaneous rank and '
                        f'file ambiguity is impossible for {chess.piece_name(self.piece_type)} at '
                        f'{chess.square_name(from_square)} moving to {chess.square_name(self.to_square)}'
                    )

                # Place the moving piece. We know exactly where it came from because of the full-square disambiguator.
                b.set_piece_at(from_square, white_piece)

                # Get candidate squares for the 2 other pieces.
                same_file_piece_candidate_squares = chess.SquareSet(
                    (
                        candidate_rect_corners
                        & chess.BB_FILES[from_file]
                        & ~chess.BB_SQUARES[from_square]
                    )
                )
                same_rank_piece_candidate_squares = chess.SquareSet(
                    (
                        candidate_rect_corners
                        & chess.BB_RANKS[from_rank]
                        & ~chess.BB_SQUARES[from_square]
                    )
                )

                # Place the other two pieces.
                for same_file_piece_square, same_rank_piece_square in itertools.product(
                    same_file_piece_candidate_squares,
                    same_rank_piece_candidate_squares,
                ):
                    b_new = b.copy()
                    b_new.set_piece_at(same_file_piece_square, white_piece)
                    b_new.set_piece_at(same_rank_piece_square, white_piece)

                    # For captures, set a black piece at `to_square`.
                    if self.is_capture:
                        b_new.set_piece_at(
                            self.to_square, chess.Piece(chess.KNIGHT, chess.BLACK)
                        )

                    # Validate that we got a position where the SAN matches exactly.
                    actual_san = b_new.san(move)
                    if actual_san != self.rendered:
                        raise RuntimeError(
                            f'Internal error: actual SAN does not match expected:\n'
                            f'actual:   {actual_san}\n'
                            f'expected: {self.rendered}'
                        )
                    yield b_new, move

            case int(from_file), None:
                # File disambiguator.

                # These will be all candidate `from_square`s.
                candidate_from_squares = chess.SquareSet(
                    to_square_attacks_mask & chess.BB_FILES[from_file]
                )

                # Get candidate squares for the other piece that can cause file ambiguity.
                candidate_other_piece_squares = chess.SquareSet(
                    to_square_attacks_mask & ~chess.BB_FILES[from_file]
                )

                # Validate that there are other files from which the same piece type could move.
                # Otherwise, there's no possibility of file ambiguity and this SAN is invalid.
                if not candidate_other_piece_squares:
                    raise ValueError(
                        f'File-disambiguated SAN {self.rendered} is impossible because no '
                        f'{chess.piece_name(self.piece_type)} that is not on the {chess.FILE_NAMES[from_file]}-file '
                        f'can move to `to_square` {chess.square_name(self.to_square)} to cause the ambiguity'
                    )

                # Iterate over possible `from_square`s
                for from_square in candidate_from_squares:
                    candidate_other_piece_squares = chess.SquareSet(
                        to_square_attacks_mask & ~chess.BB_FILES[from_file]
                    )
                    if is_slider(self.piece_type):
                        candidate_other_piece_squares &= ~extend_ray(
                            self.to_square, from_square
                        )
                    move = chess.Move(from_square, self.to_square)

                    # Place the moving piece.
                    b_from_square = b.copy()
                    b_from_square.set_piece_at(from_square, white_piece)

                    # Try all candidates for where to place the other piece.
                    for other_piece_square in candidate_other_piece_squares:
                        b_new = b_from_square.copy()
                        b_new.set_piece_at(other_piece_square, white_piece)

                        # For captures, set a black piece at `to_square`.
                        # Iterate to try all capturable black pieces in case the captured black piece
                        # restricts options for the white king. Intuitively it's probably hard or impossible
                        # for this to ever happen, but it's included for completeness.
                        if self.is_capture:
                            b_new.set_piece_at(
                                self.to_square, chess.Piece(chess.KNIGHT, chess.BLACK)
                            )

                        # Validate that we got a position where the SAN matches exactly.
                        actual_san = b_new.san(move)
                        if actual_san != self.rendered:
                            raise RuntimeError(
                                f'Internal error: actual SAN does not match expected:\n'
                                f'actual:   {actual_san}\n'
                                f'expected: {self.rendered}'
                            )
                        yield b_new, move

            case None, int(from_rank):
                # Rank disambiguator.

                # These will be all candidate `from_square`s.
                candidate_from_squares = chess.SquareSet(
                    to_square_attacks_mask & chess.BB_RANKS[from_rank]
                )

                # Validate that there is at least one file where rank ambiguity could occur.
                # Otherwise, there's no possibility of file ambiguity and this SAN is invalid.
                if not any(
                    file_candidate_from_squares_not_on_from_rank
                    for file_candidate_from_squares_not_on_from_rank in (
                        to_square_attacks_mask
                        & ~chess.BB_RANKS[from_rank]
                        & chess.BB_FILES[f]
                        for f in range(8)
                        if candidate_from_squares & chess.BB_FILES[f]
                    )
                ):
                    piece_type_name = chess.piece_name(self.piece_type)
                    raise ValueError(
                        f'Rank-disambiguated SAN {self.rendered} is impossible because no file '
                        f'which has a legal move by a {piece_type_name} from the {ordinal(from_rank)} rank '
                        f'has another square from which a {piece_type_name} can move to `to_square` '
                        f'{chess.square_name(self.to_square)} to cause the ambiguity'
                    )

                # Iterate over possible `from_square`s
                for from_square in candidate_from_squares:
                    move = chess.Move(from_square, self.to_square)
                    from_file = chess.square_file(from_square)

                    # Get candidate squares for the other piece that can cause rank ambiguity.
                    candidate_other_piece_squares = chess.SquareSet(
                        to_square_attacks_mask
                        & chess.BB_FILES[from_file]
                        & ~chess.BB_SQUARES[from_square]
                    )
                    if is_slider(self.piece_type):
                        candidate_other_piece_squares &= ~extend_ray(
                            self.to_square, from_square
                        )

                    # Place the moving piece.
                    b_from_square = b.copy()
                    b_from_square.set_piece_at(from_square, white_piece)

                    # Try all candidates for where to place the other piece.
                    for other_piece_square in candidate_other_piece_squares:
                        b_new = b_from_square.copy()
                        b_new.set_piece_at(other_piece_square, white_piece)

                        # For captures, set a black piece at `to_square`.
                        if self.is_capture:
                            b_new.set_piece_at(
                                self.to_square, chess.Piece(chess.KNIGHT, chess.BLACK)
                            )

                        # Validate that we got a position where the SAN matches exactly.
                        actual_san = b_new.san(move)
                        if actual_san != self.rendered:
                            raise RuntimeError(
                                f'Internal error: actual SAN does not match expected:\n'
                                f'actual:   {actual_san}\n'
                                f'expected: {self.rendered}'
                            )
                        yield b_new, move

            case None, None:
                # No disambiguator.

                candidate_from_squares = chess.SquareSet(to_square_attacks_mask)

                for from_square in candidate_from_squares:
                    move = chess.Move(from_square, self.to_square)
                    b_new = b.copy()
                    b_new.set_piece_at(from_square, white_piece)

                    # For captures, set a black piece at `to_square`.
                    # Iterate to try all capturable black pieces in case the captured black piece
                    # restricts options for the white king. Intuitively it's probably hard or impossible
                    # for this to ever happen, but it's included for completeness.
                    if self.is_capture:
                        b_new.set_piece_at(
                            self.to_square, chess.Piece(chess.KNIGHT, chess.BLACK)
                        )

                    actual_san = b_new.san(move)
                    if actual_san != self.rendered:
                        raise RuntimeError(
                            f'Internal error: actual SAN does not match expected:\n'
                            f'actual:   {actual_san}\n'
                            f'expected: {self.rendered}'
                        )
                    yield b_new, move

            case _:
                raise ValueError(
                    f'Invalid file/rank disambiguator combo in SAN {self.rendered}'
                )

    @property
    def can_cause_discovered_attack(self):
        if self.piece_type == chess.QUEEN:
            return False

        # Diagonal sliders cannot cause discovered attacks when the `from_square` is a corner.
        if is_diagonal_slider(self.piece_type):
            assert self.piece_type == chess.BISHOP, 'Bad logic above'
            return not all(
                move.from_square in CORNER_SQUARES
                for board, move in self.iter_positions
            )

        # Orthogonal sliders cannot cause discovered attacks when the `from_square` is on an edge.
        if is_orthogonal_slider(self.piece_type):
            assert self.piece_type == chess.ROOK, 'Bad logic above'
            return not all(
                move.from_square in EDGE_SQUARES for board, move in self.iter_positions
            )

        # Generally, moves cannot cause diagonal nor orthogonal discovered attacks when the `from_square` is a corner.
        assert self.piece_type == chess.KNIGHT, (
            'Bad logic above (possible internal error, bad state)'
        )
        return not all(
            move.from_square in CORNER_SQUARES for board, move in self.iter_positions
        )

    @property
    def moving_piece_can_cause_check(self):
        for b, move in self.iter_positions:
            occupied_before = b.occupied
            attacked_by_mask_before = attacked_by_mask(b, chess.WHITE)
            b.push(move)
            occupied_after = b.occupied
            attacked_by_mask_after = attacked_by_mask(b, chess.WHITE)
            if (
                attacked_by_mask_after
                & ~attacked_by_mask_before
                & ~(occupied_before | occupied_after)
            ):
                return True
        return False

    @classmethod
    def from_san(cls, san: str) -> NBRQSanParts:
        m = NON_PAWN_SAN_REGEX.match(san)
        if m is None:
            raise ValueError(f'Invalid non-pawn move SAN: {san}')
        piece_type = m.group('piece_type')
        file_disambiguator = m.group('file_disambiguator')
        rank_disambiguator = m.group('rank_disambiguator')
        capture = m.group('capture')
        to_square = m.group('to_square')
        check_or_mate = m.group('check_or_mate')
        try:
            piece_type = chess.Piece.from_symbol(piece_type).piece_type
            file_disambiguator = (
                chess.FILE_NAMES.index(file_disambiguator)
                if file_disambiguator is not None
                else None
            )
            rank_disambiguator = (
                chess.RANK_NAMES.index(rank_disambiguator)
                if rank_disambiguator is not None
                else None
            )
            is_capture = capture == 'x'
            to_square = chess.parse_square(to_square)
        except ValueError as e:
            raise ValueError(f'Failed to parse SAN: {san}') from e
        if piece_type not in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
            raise ValueError(
                'Invalid `piece_type`, must be knight, bishop, rook, or queen'
            )
        return cls(
            piece_type=piece_type,
            file_disambiguator=file_disambiguator,
            rank_disambiguator=rank_disambiguator,
            is_capture=is_capture,
            to_square=to_square,
            check_or_mate=check_or_mate,
        )


class KingSanParts(SanParts):
    def __init__(
        self,
        *,
        is_capture: bool = False,
        to_square: chess.Square,
        check_or_mate: str | None = None,
    ):
        super().__init__(
            piece_type=chess.KING,
            is_capture=is_capture,
            to_square=to_square,
            check_or_mate=check_or_mate,
        )

    @property
    def rendered(self) -> str:
        return (
            f'{chess.piece_symbol(self.piece_type).upper()}'
            f'{"x" if self.is_capture else ""}'
            f'{chess.square_name(self.to_square)}'
            f'{self.check_or_mate if self.check_or_mate is not None else ""}'
        )

    @property
    def iter_positions(
        self,
        *,
        place_kings: bool = True,
    ) -> Iterable[tuple[chess.Board, chess.Move]]:
        if self.check_or_mate is not None:
            raise RuntimeError(
                'This method does not yet support calling when `check_or_mate` is set'
            )

        b = chess.Board.empty()

        # Get pieces to place later.
        white_piece = chess.Piece(self.piece_type, chess.WHITE)

        # Put a piece on `to_square` and get the attacks bitboard.
        b.set_piece_at(self.to_square, white_piece)
        candidate_from_squares = chess.SquareSet(b.attacks_mask(self.to_square))
        b.remove_piece_at(self.to_square)

        for from_square in candidate_from_squares:
            move = chess.Move(from_square, self.to_square)
            b_new = b.copy()
            b_new.set_piece_at(from_square, white_piece)

            # For captures, set a black piece at `to_square`.
            if self.is_capture:
                b_new.set_piece_at(
                    self.to_square, chess.Piece(chess.KNIGHT, chess.BLACK)
                )

            actual_san = b_new.san(move)
            if actual_san != self.rendered:
                raise RuntimeError(
                    f'Internal error: actual SAN does not match expected:\n'
                    f'actual:   {actual_san}\n'
                    f'expected: {self.rendered}'
                )
            yield b_new, move

    @property
    def can_cause_discovered_attack(self):
        # King SANs should always be able to cause discovered check because disambiguators are disallowed
        # (no multiple kings in standard chess), meaning the `from_square` is never fully specified as a corner square
        # and therefore the king could come from any neighboring square.
        # The `from_square` options are most restricted for a king when the `to_square` (which we know) is a corner,
        # But in those cases the `from_square` could always be one of b2/b7/g2/g7, which are non-corners.
        # Therefore, discovered checks are always possible.
        assert not all(
            move.from_square in CORNER_SQUARES for board, move in self.iter_positions
        ), 'Expected king moves to always be able to cause discovered attacks'
        return True

    @property
    def moving_piece_can_cause_check(self):
        # A king causing check would mean stepping into check
        return False

    @classmethod
    def from_san(cls, san: str) -> KingSanParts:
        m = NON_PAWN_SAN_REGEX.match(san)
        if m is None:
            raise ValueError(f'Invalid SAN: {san}')
        piece_type = m.group('piece_type')
        file_disambiguator = m.group('file_disambiguator')
        rank_disambiguator = m.group('rank_disambiguator')
        if file_disambiguator or rank_disambiguator:
            raise ValueError('King moves cannot have disambiguators')
        capture = m.group('capture')
        to_square = m.group('to_square')
        check_or_mate = m.group('check_or_mate')
        try:
            piece_type = chess.Piece.from_symbol(piece_type).piece_type
            is_capture = capture == 'x'
            to_square = chess.parse_square(to_square)
        except ValueError as e:
            raise ValueError(f'Failed to parse SAN: {san}') from e
        if piece_type != chess.KING:
            raise ValueError(
                f'Piece type must be king, not {chess.piece_name(piece_type)}'
            )
        return cls(
            is_capture=is_capture,
            to_square=to_square,
            check_or_mate=check_or_mate,
        )


if __name__ == '__main__':
    for san in ('axb2',):
        print('=' * (len(san) + 6))
        print(f'{san = }')
        print('=' * (len(san) + 6))
        san_parts = SanParts.from_san(san)
        for board, move in san_parts.iter_positions:
            print(board)
            print(f'move: {board.san(move)}')
            print('---')
        print()
