// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.18;

interface Token {
    function balanceOf(address _owner) external view returns (uint256 balance);

    function transfer(
        address _to,
        uint256 _value
    ) external returns (bool success);

    function transferFrom(
        address _from,
        address _to,
        uint256 _value
    ) external returns (bool success);

    function approve(
        address _spender,
        uint256 _value
    ) external returns (bool success);

    function allowance(
        address _owner,
        address _spender
    ) external view returns (uint256 remaining);

    event Transfer(address indexed _from, address indexed _to, uint256 _value);
    event Approval(
        address indexed _owner,
        address indexed _spender,
        uint256 _value
    );
}

interface WETH {
    function deposit() external payable;

    function withdraw(uint256 amount) external;
}

interface Pair {
    function getReserves()
        external
        view
        returns (uint112 reserve0, uint112 reserve1, uint32 blockTimestampLast);

    function swap(
        uint amount0Out,
        uint amount1Out,
        address to,
        bytes calldata data
    ) external;
}

interface ArbRouter {
    function unwrap_withdraw(uint256 amount, address wbnb) external;

    function withdraw(uint256 amount, address token) external;
}

abstract contract RouterMulticall {
    address private immutable admin;
    address private immutable router;

    constructor(address _router) {
        admin = msg.sender;
        router = _router;
    }

    modifier onlyAdmin() {
        require(msg.sender == admin, "Unauthorized");
        _;
    }

    function getAmountOut(
        uint amountIn,
        uint reserveIn,
        uint reserveOut,
        uint16 feeNumerator
    ) private pure returns (uint amountOut) {
        uint amountInWithFee = amountIn * feeNumerator;
        uint numerator = amountInWithFee * reserveOut;
        uint denominator = reserveIn * 10000 + amountInWithFee;
        amountOut = numerator / denominator;
    }

    function multi_unwrap_withdraw(
        uint256 amount0,
        address wbnb0,
        uint256 amount1,
        address wbnb1
    ) external {
        ArbRouter(router).unwrap_withdraw(amount0, wbnb0);
        ArbRouter(router).unwrap_withdraw(amount1, wbnb1);
    }

    function withdraw_swap_unwrap(
        uint112 amountIn,     // 0-14
        address pair,         // 14-34
        uint16 feeNumerator,  // 34-36
        bool is0in,           // 36-37
        uint112 minAmountOut, // 37-51
        address token,        // 51-71
        address weth          // 71-91
    ) external onlyAdmin {
        uint112 reserveIn;
        uint112 reserveOut;
        if (is0in) (reserveIn, reserveOut, ) = Pair(pair).getReserves();
        else (reserveOut, reserveIn, ) = Pair(pair).getReserves();

        uint256 amountOut = getAmountOut(
            amountIn,
            reserveIn,
            reserveOut,
            feeNumerator
        );

        require(amountOut >= minAmountOut, "Low amount out");

        ArbRouter(router).withdraw(amountIn, token);

        Token(token).transferFrom(tx.origin, pair, amountIn);

        if (is0in) Pair(pair).swap(0, amountOut, address(this), "");
        else Pair(pair).swap(amountOut, 0, address(this), "");

        WETH(weth).withdraw(amountOut);
        payable(msg.sender).transfer(amountOut);
    }
}
