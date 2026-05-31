# 2024-06-vultisig Report

## [H-01] Most users won’t be able to claim their share of Uniswap fees

*Submitted by juancito, also found by Bigsam, crypticdefense, tobi0x18, rspadi, Chinmay, 0x04bytes, KupiaSec, Audinarey, h2134, HChang26, kennedy1030, Ryonen, rbserver, and shaflow2*

Users should be able to claim Uniswap fees for their current liquidity position regardless of their pending vestings, or cliff. But most users won’t be able to claim those Uniswap fees.

It is also possible that they won’t be able to claim their vesting if they accumulate sufficient unclaimed Uniswap fees.

The root issue is that the `claim()` function collects ALL the owed tokens at once, including the ones from the burnt liquidity, but also the fees corresponding to ALL positions:

```
    (uint128 amountCollected0, uint128 amountCollected1) = pool.collect(
        address(this),
        TICK_LOWER,
        TICK_UPPER,
@>      type(uint128).max,
@>      type(uint128).max
    );
```

[https://github.com/code-423n4/2024-06-vultisig/blob/main/src/ILOPool.sol#L246-L247](https://github.com/code-423n4/2024-06-vultisig/blob/main/src/ILOPool.sol#L246-L247)

Then the platform fees are sent alongside the Uniswap fees from the users that still didn’t claim `amountCollected - amount` :

```
TransferHelper.safeTransfer(_cachedPoolKey.token0, feeTaker, amountCollected0-amount0);
TransferHelper.safeTransfer(_cachedPoolKey.token1, feeTaker, amountCollected1-amount1);
```

[https://github.com/code-423n4/2024-06-vultisig/blob/main/src/ILOPool.sol#L252-L260](https://github.com/code-423n4/2024-06-vultisig/blob/main/src/ILOPool.sol#L252-L260)

The next time a user calls `claim()` , `pool.collect()` will not contain any Uniswap fees as all of them have already been claimed and sent to the first claimer and the rest to the fee taker. If the platform fees are enough to cover the owed fees for the claiming user, the transaction might succeed (this may be possible if the burnt liquidity is enough).

As time passes, more fees will be accumulated, and when Uniswap fees `>` platform fees, the transaction will also revert even for unclaimed vestings with liquidity to burn. In addition, in most cases after the initial vesting, users won’t be able to claim Uniswap fees, as no fees will be collected, and the contract doesn’t hold those assets (they have been sent to the fee taker).

This POC shows how after one user claims their share of the fees, there are no more fee tokens to collect for the next claims, and the transactions revert.

1. Add the import to the top of test/ILOPool.t.sol.
2. Add the test to the ILOPoolTest contract in test/ILOPool.t.sol.
3. Run forge test --mt testClaimFeesRevert.

```
import '../lib/v3-core/contracts/interfaces/IUniswapV3Pool.sol';
```

```
function testClaimFeesRevert() external {
    _launch();
    vm.warp(VEST_START_0 + 10);

    uint256 tokenId = IILOPool(iloPool).tokenOfOwnerByIndex(INVESTOR, 0);
    uint256 tokenId2 = IILOPool(iloPool).tokenOfOwnerByIndex(INVESTOR_2, 0);

    IUniswapV3Pool uniV3Pool = IUniswapV3Pool(projectId);

    // INVESTOR and INVESTOR_2 burn their liquidity and obtain their tokens

    vm.prank(INVESTOR);
    IILOPool(iloPool).claim(tokenId);

    vm.prank(INVESTOR_2);
    IILOPool(iloPool).claim(tokenId2);

    // Generate some fees via a flash loan
    uniV3Pool.flash(address(this), 1e8, 1e8, "");

    // INVESTOR claims their corresponding part of the fees
    // Only the first one to claim has better odds of claiming successfully
    vm.prank(INVESTOR);
    IILOPool(iloPool).claim(tokenId);

    // INVESTOR_2 can't claim their part of the fees as the transaction will revert
    // It reverts with ST (SafeTransfer) as it is trying to transfer tokens the contract doesn't have
    // The fees for INVESTOR_2 were already taken
    vm.prank(INVESTOR_2);
    vm.expectRevert(bytes("ST"));
    IILOPool(iloPool).claim(tokenId2);

    // Generate more fees
    uniV3Pool.flash(address(this), 1e6, 1e6, "");

    // Even if some new fees are available, they might not be enough to pay back the owed ones to INVESTOR_2
    vm.prank(INVESTOR_2);
    vm.expectRevert(bytes("ST"));
    IILOPool(iloPool).claim(tokenId2);
}

function uniswapV3FlashCallback(uint256, uint256, bytes memory) external {
    deal(USDC, address(this), IERC20(USDC).balanceOf(address(this)) * 2);
    deal(SALE_TOKEN, address(this), IERC20(SALE_TOKEN).balanceOf(address(this)) * 2);

    IERC20(USDC).transfer(projectId, IERC20(USDC).balanceOf(address(this)));
    IERC20(SALE_TOKEN).transfer(projectId, IERC20(SALE_TOKEN).balanceOf(address(this)));
}
```

Here’s an suggestion on how this could be solved. The idea is to only `collect()` the tokens corresponding to the liquidity of the `tokenId` position. So that the next user can also claim their share.

```
    function claim(uint256 tokenId) external payable override isAuthorizedForToken(tokenId)
        returns (uint256 amount0, uint256 amount1)
    {
+       uint128 collect0;
+       uint128 collect1;

        uint128 liquidity2Claim = _claimableLiquidity(tokenId);
        IUniswapV3Pool pool = IUniswapV3Pool(_cachedUniV3PoolAddress);
        {
            IILOManager.Project memory _project = IILOManager(MANAGER).project(address(pool));
            uint128 positionLiquidity = position.liquidity;

            // get amount of token0 and token1 that pool will return for us
            (amount0, amount1) = pool.burn(TICK_LOWER, TICK_UPPER, liquidity2Claim);

+           collect0 = amount0;
+           collect1 = amount1;

            // get amount of token0 and token1 after deduct platform fee
            (amount0, amount1) = _deductFees(amount0, amount1, _project.platformFee);

            ...

            uint256 fees0 = FullMath.mulDiv(
                            feeGrowthInside0LastX128 - position.feeGrowthInside0LastX128,
                            positionLiquidity,
                            FixedPoint128.Q128
                        );
            
            uint256 fees1 = FullMath.mulDiv(
                                feeGrowthInside1LastX128 - position.feeGrowthInside1LastX128,
                                positionLiquidity,
                                FixedPoint128.Q128
                            );

+           collect0 += fees0;
+           collect1 += fees1;

            // amount of fees after deduct performance fee
            (fees0, fees1) = _deductFees(fees0, fees1, _project.performanceFee);

            ...
        }

        (uint128 amountCollected0, uint128 amountCollected1) = pool.collect(
            address(this),
            TICK_LOWER,
            TICK_UPPER,
-           type(uint128).max,
-           type(uint128).max
+           collect0,
+           collect1
        );
        
        ...
    }
```

Uniswap

**0xsomeone (judge) commented:**

> The Warden outlines an issue with the fee collection mechanism whenever a position is claimed that would result in the contract claiming more funds than the user is due and the fee taker acquiring this difference.
> In turn, this will result in all consequent claim operations of other NFT IDs on the same tick range (i.e., the same pool) to fail potentially permanently due to being unable to capture the fee-related portion. I consider this to be a significant flaw and one that merits a high-risk severity rating.

**Haupc (Vultisig) confirmed**


## [H-03] Adversary can prevent the launch of any ILO pool with enough raised capital at any moment by providing single-sided liquidity

*Submitted by juancito, also found by nnez, iam_emptyset, and 0xc0ffEE*

[https://github.com/code-423n4/2024-06-vultisig/blob/main/src/ILOPool.sol#L296](https://github.com/code-423n4/2024-06-vultisig/blob/main/src/ILOPool.sol#L296)

It is possible to prevent the launch of any ILO pool at any time, including pools that have reached their total raised amount. This can be done at any time and the cost for the attacker is negligible.

Not only this is a DOS of the whole protocol, but the attack can be performed at the very end of the sale, making users lose a lot on gas fees, considering it will be deployed on Ethereum Mainnet. Hundreds or thousands of users will participate in ILO pools via `buy()` , and will have to later call `claimRefund()` to get their “raise” tokens back.

Token launches that were deemed to be successful will be blocked after raising funds from many users, and this will most certainly affect the perception of the token, and its pricing on any attempt of a future launch/sale.

The `ILOManager` contract has a check to assert that the price at the time of the token launch is the same as the one initialized by the project. If they differ the transaction will revert, and the token launch will fail:

```
function launch(address uniV3PoolAddress) external override {
    require(block.timestamp > _cachedProject[uniV3PoolAddress].launchTime, "LT");
    (uint160 sqrtPriceX96, , , , , , ) = IUniswapV3Pool(uniV3PoolAddress).slot0();
@>  require(_cachedProject[uniV3PoolAddress].initialPoolPriceX96 == sqrtPriceX96, "UV3P");
    address[] memory initializedPools = _initializedILOPools[uniV3PoolAddress];
    require(initializedPools.length > 0, "NP");
    for (uint256 i = 0; i < initializedPools.length; i++) {
        IILOPool(initializedPools[i]).launch();
    }

    emit ProjectLaunch(uniV3PoolAddress);
}
```

[https://github.com/code-423n4/2024-06-vultisig/blob/main/src/ILOManager.sol#L190](https://github.com/code-423n4/2024-06-vultisig/blob/main/src/ILOManager.sol#L190)

The problem is that `sqrtPriceX96` can be easily manipulated in Uniswap v3 Pools when there is no liquidity in it via a swap with no cost. In theory, this could be mitigated by anyone by swapping back to get back to the original price. But there is an additional problem which makes the severity of the attack even higher. The attacker can add [single-sided liquidity](https://support.uniswap.org/hc/en-us/articles/20902968738317-What-is-single-sided-liquidity#:~:text=When%20you%20select%20a%20range%20that%20is%20outside%20the%20current%20price%20range%2C%20you%20will%20only%20be%20able%20to%20supply%20one%20of%20the%20two%20tokens.) to the pool (just the Raise Token) after the price was manipulated.

> When you select a range that is outside the current price range, you will only be able to supply one of the two tokens.

By adding liquidity in ticks greater than the manipulated price, but lower than the expected initial price, it would require the swapper to provide some `SALE_TOKEN` , which should not be available at this moment, since they should all be in the ILO pool.

Even if the project admin has some `SALE_TOKEN` , the attacker can mint a higher amount of liquidity by providing more single-sided `RAISE_TOKEN` liquidity, making the needed amount of `SALE_TOKEN` even higher.

The following Proof of Concept shows how an attacker can make a launch revert after raising capital, at the cost of providing liquidity with only `1 wei` of USDC (Raise Token).

Console Output:

```
<<Minting Attack>>
<<Failed mitigation attempt>>
  
uniswapV3SwapCallback()
  amount0 (USDC)       0
  amount1 (SALE_TOKEN) 1
```

This would be enough to perform an attack that can’t be reverted in most cases since no other sale tokens should be circulating before the launch. But for the sake of interest, the minted liquidity and the mitigation amount can be increased to check the values needed to get back to the initial price in different situations.

POC:

1. Add the import to the top of test/ILOManager.t.sol.
2. Add the test to the ILOManagerTest contract in test/ILOManager.t.sol.
3. Run forge test --mt testManipulatePriceForLaunch -vv.

Since the price can be manipulated, and single-sided liquidity can be minted, getting the price back to its initial price would require swapping and providing `SALE_TOKEN` . Since it’s an initial sale with vesting for other participants, it is expected that no parties hold the token. But, even if they do, the attack can be performed at some cost anyway as explained before.

So one possible solution could be to reserve some amount in the ILO pool in case it needs to be swapped back, and perform a swap before the liquidity is added to the Uniswap Pool, taking into account an amount that would make the attack very expensive to rollback. Another approach could involve having a wrapper token around the `SALE_TOKEN` that can be minted and swapped to reach the expected price.

This is a potential first step. Additional considerations shall be taken into account, like an attacker minting liquidity on various tick ranges, which may also affect calculations.

Uniswap

**Haupc (Vultisig) confirmed**
