// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.18;

interface ERC20 {
    function balanceOf(address) external view returns (uint256);
}

contract BatchCheckerV4 {
    function _checkArb(address router, bytes calldata arbCall) external {
        unchecked {
            uint256 selector = uint256(uint8(arbCall[0]));
            address tokenOut;
            uint256 balanceBefore;

            // GETTING BALANCE BEFORE
            // swap 2 same
            if (selector == 1) {
                assembly {
                    tokenOut := shr(89, calldataload(177))
                }
                balanceBefore = ERC20(tokenOut).balanceOf(router);
            }
            // swap 2 different
            else if (selector == 2) {
                address tokenIn;
                uint256 amountIn;

                assembly {
                    tokenOut := shr(89, calldataload(219))
                    tokenIn := shr(89, calldataload(177))
                    amountIn := shr(144, calldataload(122))
                }

                balanceBefore = ERC20(tokenOut).balanceOf(router);

                if (ERC20(tokenIn).balanceOf(router) >= amountIn)
                    balanceBefore += amountIn;
            }
            // swap 3 same
            else if (selector == 3) {
                assembly {
                    tokenOut := shr(89, calldataload(201))
                }
                balanceBefore = ERC20(tokenOut).balanceOf(router);
            }
            // swap 3 different
            else {
                address tokenIn;
                uint256 amountIn;

                assembly {
                    tokenOut := shr(89, calldataload(243))
                    tokenIn := shr(89, calldataload(201))
                    amountIn := shr(144, calldataload(122))
                }

                balanceBefore = ERC20(tokenOut).balanceOf(router);

                if (ERC20(tokenIn).balanceOf(router) >= amountIn)
                    balanceBefore += amountIn;
            }

            uint256 gasBefore = gasleft();
            (bool success, ) = router.call(arbCall);
            uint256 gasAfter = gasleft();

            assembly {
                // revert
                if iszero(success) {
                    mstore(0, 0)
                    revert(0, 19)
                }
                // no profit
                if gt(returndatasize(), 0) {
                    mstore(0, hex"01")
                    revert(0, 19)
                }
            }

            uint256 balanceAfter = ERC20(tokenOut).balanceOf(router);

            assembly {
                // success
                if gt(balanceAfter, balanceBefore) {
                    mstore(
                        0,
                        add(
                            hex"01",
                            add(
                                shl(136, sub(balanceAfter, balanceBefore)),
                                shl(104, sub(gasBefore, gasAfter))
                            )
                        )
                    )
                    revert(0, 19)
                }

                // weird case where router didn't detect nonprofitable tx
                mstore(0, shl(104, sub(gasBefore, gasAfter)))
                revert(0, 19)
            }
        }
    }

    function checkArbs(address router, bytes[] calldata arbData)
        external
        returns (bytes memory results)
    {
        unchecked {
            for (uint256 i; i < arbData.length; i++) {
                try this._checkArb(router, arbData[i]) {} catch (
                    bytes memory result
                ) {
                    results = bytes.concat(results, result);
                }
            }
        }
    }
}
