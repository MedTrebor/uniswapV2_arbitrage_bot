object "RouterMulticall" {
    // router 0x5573751b3e18848691896bbeab396fc8ac2a579b
    // bot 0x0fed3a25eee9d525a5671b5995fd489fcd
    // Unauthorized() 0x82b42900
    // WithdrawError() 0xd4771574
    // getReserves() 0x0902f1ac
    // LowAmountOut() 0x7f3ab553
    // transferFrom(from, to, amount) 0x23b872dd
    // transferError() 0xef992d59
    // swap(amount0Out, amount1Out, to, data) 0x022c0d9f
    // SwapError() 0x7c3eb9ca
    // withdraw(amount) 0x2e1a7d4d
    code {
        datacopy(returndatasize(), dataoffset("runtime"), datasize("runtime"))
        // datacopy(returndatasize(), dataoffset("runtime"), add(20, datasize("runtime")))

        // args packed: router address, admin address
        // setimmutable(returndatasize(), "router", shr(96, mload(datasize("runtime"))))
        // router 0x9f4353f41dB970A15120Bf9b130B62F872D6bC8e

        return(returndatasize(), datasize("runtime"))
    }

    object "runtime" {
        code {
            if gt(callvalue(), 0) {
                stop()
            }
            // auth
            if xor(caller(), 0x0fed3a25eee9d525a5671b5995fd489fcd) {
                mstore(returndatasize(), 0x82b42900)
                revert(28, 4)
            }

            // MULTI UNWRAP WITHDRAW
            if gt(calldatasize(), 91) {
                // loading first withdraw arguments: amount and weth address
                calldatacopy(1, callvalue(), 52)

                // executing withdraw
                if iszero(
                    call(
                        gas(),
                        0x9f4353f41dB970A15120Bf9b130B62F872D6bC8e,
                        callvalue(),
                        callvalue(),
                        53,
                        callvalue(),
                        callvalue() 
                    )
                ) {
                    mstore(callvalue(), 0xd4771574)
                    revert(28, 4)
                }

                // loading second arguments
                calldatacopy(1, 52, 52)

                // executing withdraw
                if iszero(
                    call(
                        gas(),
                        0x9f4353f41dB970A15120Bf9b130B62F872D6bC8e,
                        callvalue(),
                        callvalue(),
                        53,
                        callvalue(),
                        callvalue() 
                    )
                ) {
                    mstore(callvalue(), 0xd4771574)
                    revert(28, 4)
                }
                stop()
            }

            // WITHDRAW SWAP UNWRAP
            // getting reserves
            mstore(callvalue(), 0x0902f1ac)
            let pair := shr(96, calldataload(14))

            pop(
                staticcall(
                    gas(),
                    pair,
                    28,
                    4,
                    callvalue(),
                    64
                )
            )

            // getting amount out
            let amountIn := shr(144, calldataload(callvalue()))

            let amountInFee := mul(
                shr(240, calldataload(34)),
                amountIn
            )
            let is0in := shr(248, calldataload(36))
            
            let amountOut

            switch is0in
                case 0 {
                    amountOut := div(
                        mul(amountInFee, mload(callvalue())),
                        add(mul(mload(32), 10000), amountInFee)
                    )
                }
                default {
                    amountOut := div(
                        mul(amountInFee, mload(32)),
                        add(mul(mload(callvalue()), 10000), amountInFee)
                    )
                }


            // error if below minimum amount out
            if gt(shr(144, calldataload(37)), amountOut) {
                mstore(callvalue(), 0x7f3ab553)
                revert(28, 4)
            }
            
            // storing withraw arguments
            calldatacopy(64, 51, 20)
            mstore(callvalue(), 0x14)
            mstore(32, amountIn)

            // withdrawing from router
            if iszero(
                call(
                    gas(),
                    0x9f4353f41dB970A15120Bf9b130B62F872D6bC8e,
                    callvalue(),
                    31,
                    53,
                    callvalue(),
                    callvalue()
                )
            ) {
                mstore(callvalue(), 0xd4771574)
                revert(28, 4)
            }

            // transfering to pair
            mstore(callvalue(), 0x23b872dd)
            mstore(32, caller())
            mstore(64, pair)
            mstore(96, amountIn)

            if iszero(
                call(
                    gas(),
                    calldataload(39),
                    callvalue(),
                    28,
                    132,
                    callvalue(),
                    callvalue()
                )
            ) {
                mstore(callvalue(), 0xef992d59)
                revert(28, 4)
            }

            // storing selector, to and data swap arguments
            mstore(callvalue(), 0x022c0d9f)
            mstore(96, address())
            mstore(128, 128)

            // storing amounts out
            switch is0in
            case 0 {
                mstore(32, amountOut)
                mstore(64, callvalue())
            }
            default {
                mstore(32, callvalue())
                mstore(64, amountOut)
            }

            // swapping
            if iszero(
                call(
                    gas(),
                    pair,
                    callvalue(),
                    28,
                    164,
                    callvalue(),
                    callvalue()
                )
            ) {
                mstore(callvalue(), 0x7c3eb9ca)
                revert(28, 4)
            }

            // withdrawing weth
            mstore(callvalue(), 0x2e1a7d4d)
            mstore(32, amountOut)
            if iszero(
                call(
                    gas(),
                    calldataload(59),
                    callvalue(),
                    28,
                    36,
                    callvalue(),
                    callvalue()
                )
            ) {
                mstore(callvalue(), 0xd4771574)
                revert(28, 4)
            }

            // sending eth to caller
            pop(
                call(
                    gas(),
                    caller(),
                    amountOut,
                    callvalue(),
                    callvalue(),
                    callvalue(),
                    callvalue()
                )
            )
            stop()
        }
    }
}