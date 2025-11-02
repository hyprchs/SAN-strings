import chess

from chess_action_space import iter_action_space
from san_strings.constants import PROMOTION_PIECE_TYPES
from san_strings.utils import (
    can_be_king_move,
    can_be_nbrq_move_by,
    can_be_pawn_move,
    can_require_file_disambiguator,
    can_require_full_square_disambiguator,
    can_require_rank_disambiguator,
)
from san_strings.utils.san_parts import (
    KingSanParts,
    NBRQSanParts,
    PawnSanParts,
    SanParts,
)

_b = chess.Board.empty()
""" A blank `chess.Board` to use for generating moves. """


def gen_sans() -> set[str]:
    sans: set[str] = set()

    for move in iter_action_space():
        move_sans: set[str] = set()

        def add_san(san_parts: SanParts) -> None:
            san_parts = san_parts.copy()
            if san_parts.check_or_mate is not None:
                raise ValueError('Should only pass non-check/mate `SanParts`')
            move_sans.add(san_parts.rendered)
            if san_parts.can_cause_check:
                # TODO: Prove that a SAN can cause check if and only if it can cause checkmate
                san_parts.check_or_mate = '+'
                move_sans.add(san_parts.rendered)
                san_parts.check_or_mate = '#'
                move_sans.add(san_parts.rendered)

        # Set vars we might use later.
        from_file = chess.square_file(move.from_square)
        from_rank = chess.square_rank(move.from_square)

        #################
        #     Pawns     #
        #################
        if can_be_pawn_move(
            move,
            enforce_is_capture_as=False,
            enforce_is_promotion_as=False,
        ):
            add_san(PawnSanParts(to_square=move.to_square))

        if can_be_pawn_move(
            move,
            enforce_is_capture_as=True,
            enforce_is_promotion_as=False,
        ):
            add_san(
                PawnSanParts(
                    file_disambiguator=from_file,
                    to_square=move.to_square,
                    is_capture=True,
                )
            )

        if can_be_pawn_move(
            move,
            enforce_is_capture_as=False,
            enforce_is_promotion_as=True,
        ):
            for promotion_piece_type in PROMOTION_PIECE_TYPES:
                add_san(
                    PawnSanParts(
                        to_square=move.to_square,
                        promotion_piece_type=promotion_piece_type,
                    )
                )

        if can_be_pawn_move(
            move,
            enforce_is_capture_as=True,
            enforce_is_promotion_as=True,
        ):
            for promotion_piece_type in PROMOTION_PIECE_TYPES:
                add_san(
                    PawnSanParts(
                        file_disambiguator=from_file,
                        is_capture=True,
                        to_square=move.to_square,
                        promotion_piece_type=promotion_piece_type,
                    )
                )

        #################
        #     Kings     #
        #################
        # Non-castling
        if can_be_king_move(
            move,
            enforce_is_kingside_castling_as=False,
            enforce_is_queenside_castling_as=False,
        ):
            add_san(KingSanParts(to_square=move.to_square))
            # Capture king moves are trivially possible when non-capture is possible - TODO: prove with FENs
            add_san(KingSanParts(is_capture=True, to_square=move.to_square))

        # Kingside castling
        if can_be_king_move(
            move,
            enforce_is_kingside_castling_as=True,
            enforce_is_queenside_castling_as=False,
        ):
            san = 'O-O'
            move_sans.add(san)
            # Capture/check castling SANs are trivially possible - TODO: prove with FENs
            move_sans.add(f'{san}+')
            move_sans.add(f'{san}#')

        # Queenside castling
        if can_be_king_move(
            move,
            enforce_is_kingside_castling_as=False,
            enforce_is_queenside_castling_as=True,
        ):
            san = 'O-O-O'
            move_sans.add(san)
            # Capture/check castling SANs are trivially possible - TODO: prove with FENs
            move_sans.add(f'{san}+')
            move_sans.add(f'{san}#')

        ########################################
        #     Knights/Bishops/Rooks/Queens     #
        ########################################
        for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
            if can_be_nbrq_move_by(piece_type, move):
                # Non-disambiguated
                #   - captures
                #   - capture checks
                #   - capture checkmates
                #   - non-capture checks
                #   - non-capture checkmates
                # are trivially always possible for these piece types.
                # This is because non-disambiguated moves can always cause new squares to be attacked.
                # TODO: Prove with FENs
                add_san(NBRQSanParts(piece_type=piece_type, to_square=move.to_square))
                add_san(
                    NBRQSanParts(
                        piece_type=piece_type, is_capture=True, to_square=move.to_square
                    )
                )

                for is_capture in (False, True):
                    if can_require_file_disambiguator(move=move, piece_type=piece_type):
                        add_san(
                            NBRQSanParts(
                                piece_type=piece_type,
                                file_disambiguator=from_file,
                                is_capture=is_capture,
                                to_square=move.to_square,
                            )
                        )

                    if can_require_rank_disambiguator(move=move, piece_type=piece_type):
                        add_san(
                            NBRQSanParts(
                                piece_type=piece_type,
                                rank_disambiguator=from_rank,
                                is_capture=is_capture,
                                to_square=move.to_square,
                            )
                        )

                    if can_require_full_square_disambiguator(
                        move=move,
                        piece_type=piece_type,
                    ):
                        add_san(
                            NBRQSanParts(
                                piece_type=piece_type,
                                file_disambiguator=from_file,
                                rank_disambiguator=from_rank,
                                is_capture=is_capture,
                                to_square=move.to_square,
                            )
                        )

        assert move_sans, f'Action {move} did not generate any SANs'
        sans.update(move_sans)

    return sans


def main():
    all_sans = gen_sans()

    def sort_key(s: str) -> tuple:
        def is_check(s):
            return s.endswith('+')

        def is_mate(s):
            return s.endswith('#')

        def is_plain(s):
            return not is_check(s) and not is_mate(s)

        return is_mate(s), is_check(s), is_plain(s), len(s), s

    all_sans = sorted(all_sans, key=sort_key)

    with open('san_strings.txt', 'w') as f:
        f.write('\n'.join(san for san in all_sans if '+' not in san and '#' not in san))

    with open('san_strings_with_symbols.txt', 'w') as f:
        f.write('\n'.join(all_sans))

    print('Done!')


if __name__ == '__main__':
    main()
