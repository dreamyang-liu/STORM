// SPDX-License-Identifier: BUSL-1.1
pragma solidity ^0.8.0;

import 'src/libraries/helpers/Constants.sol';
import 'src/libraries/helpers/Errors.sol';

import 'test/helpers/TestUser.sol';
import 'test/setup/TestWithIsolateAction.sol';

contract TestIntIsolateLiquidate is TestWithIsolateAction {
  struct TestCaseLocalVars {
    uint256 poolBalanceBefore;
    uint256 poolBalanceAfter;
    // 1 - liquidator, 2 - borrower
    uint256 walletBalanceBefore1;
    uint256 walletBalanceBefore2;
    uint256 walletBalanceAfter1;
    uint256 walletBalanceAfter2;
    uint256 erc721BalanceBefore1;
    uint256 erc721BalanceAfter1;
    TestLoanData[] loanDataBefore;
    TestLoanData[] loanDataAfter;
    uint256 txAuctionTimestamp;
    uint256 totalBorrowAmount;
    uint256 totalBidAmount;
    uint256 totalBidFine;
    uint256 totalRedeemAmount;
  }

  function onSetUp() public virtual override {
    super.onSetUp();

    initCommonPools();
  }

  function prepareBorrow(TestUser user, address nftAsset, uint256[] memory tokenIds, address debtAsset) internal {
    TestLoanData memory loanDataBeforeBorrow = getIsolateCollateralData(tsCommonPoolId, nftAsset, 0, debtAsset);

    uint256[] memory borrowAmounts = new uint256[](tokenIds.length);
    for (uint256 i = 0; i < tokenIds.length; i++) {
      borrowAmounts[i] = loanDataBeforeBorrow.availableBorrow - (i + 1);
    }

    user.isolateBorrow(tsCommonPoolId, nftAsset, tokenIds, debtAsset, borrowAmounts, address(user), address(user));
  }

  function prepareAuction(TestUser user, address nftAsset, uint256[] memory tokenIds, address debtAsset) internal {
    user.approveERC20(debtAsset, type(uint256).max);

    uint256[] memory bidAmounts = new uint256[](tokenIds.length);
    for (uint256 i = 0; i < tokenIds.length; i++) {
      TestLoanData memory loanDataBeforeAuction = getIsolateLoanData(tsCommonPoolId, nftAsset, tokenIds[i]);
      assertLt(loanDataBeforeAuction.healthFactor, 1e18, 'healthFactor not lt 1');
      bidAmounts[i] = (loanDataBeforeAuction.borrowAmount * 1011) / 1000;
    }

    user.isolateAuction(tsCommonPoolId, nftAsset, tokenIds, debtAsset, bidAmounts);
  }

  function test_Should_LiquidateWETH() public {
    TestCaseLocalVars memory testVars;

    // deposit
    prepareWETH(tsDepositor1);
    uint256[] memory tokenIds = prepareIsolateBAYC(tsBorrower1);

    // borrow
    prepareBorrow(tsBorrower1, address(tsBAYC), tokenIds, address(tsWETH));

    // make some interest
    advanceTimes(365 days);

    // drop down nft price
    actionSetNftPrice(address(tsBAYC), 5000);

    // auction
    prepareAuction(tsLiquidator1, address(tsBAYC), tokenIds, address(tsWETH));

    // end the auction
    advanceTimes(25 hours);

    uint256[] memory liquidateAmounts = new uint256[](tokenIds.length);
    testVars.loanDataBefore = getIsolateLoanData(tsCommonPoolId, address(tsBAYC), tokenIds);
    for (uint256 i = 0; i < tokenIds.length; i++) {
      testVars.totalBidAmount += testVars.loanDataBefore[i].bidAmount;
      testVars.totalBidFine += testVars.loanDataBefore[i].bidFine;
      testVars.totalRedeemAmount += testVars.loanDataBefore[i].redeemAmount;
      testVars.totalBorrowAmount += testVars.loanDataBefore[i].borrowAmount;
    }

    testVars.poolBalanceBefore = tsWETH.balanceOf(address(tsPoolManager));
    testVars.walletBalanceBefore1 = tsWETH.balanceOf(address(tsLiquidator1));
    testVars.walletBalanceBefore2 = tsWETH.balanceOf(address(tsBorrower1));
    testVars.erc721BalanceBefore1 = tsBAYC.balanceOf(address(tsLiquidator1));

    // liquidate
    tsLiquidator1.isolateLiquidate(tsCommonPoolId, address(tsBAYC), tokenIds, address(tsWETH), liquidateAmounts, false);
    testVars.txAuctionTimestamp = block.timestamp;

    // check results
    testVars.loanDataAfter = getIsolateLoanData(tsCommonPoolId, address(tsBAYC), tokenIds);
    for (uint256 i = 0; i < tokenIds.length; i++) {
      assertEq(testVars.loanDataAfter[i].bidStartTimestamp, 0, 'bidStartTimestamp');
      assertEq(testVars.loanDataAfter[i].firstBidder, address(0), 'firstBidder');
      assertEq(testVars.loanDataAfter[i].lastBidder, address(0), 'lastBidder');
      assertEq(testVars.loanDataAfter[i].bidAmount, 0, 'bidAmount');
      assertEq(testVars.loanDataAfter[i].borrowAmount, 0, 'borrowAmount');
    }

    testVars.poolBalanceAfter = tsWETH.balanceOf(address(tsPoolManager));
    assertEq(
      testVars.poolBalanceAfter,
      testVars.poolBalanceBefore - (testVars.totalBidAmount - testVars.totalBorrowAmount),
      'tsPoolManager weth balance'
    );

    testVars.walletBalanceAfter1 = tsWETH.balanceOf(address(tsLiquidator1));
    assertEq(testVars.walletBalanceAfter1, testVars.walletBalanceBefore1, 'tsLiquidator1 weth balance');

    testVars.walletBalanceAfter2 = tsWETH.balanceOf(address(tsBorrower1));
    assertEq(
      testVars.walletBalanceAfter2,
      (testVars.walletBalanceBefore2 + (testVars.totalBidAmount - testVars.totalBorrowAmount)),
      'tsBorrower1 balance'
    );

    testVars.erc721BalanceAfter1 = tsBAYC.balanceOf(address(tsLiquidator1));
    assertEq(
      testVars.erc721BalanceAfter1,
      (testVars.erc721BalanceBefore1 + tokenIds.length),
      'tsLiquidator1 bayc balance'
    );
  }

  function test_Should_LiquidateUSDT_SupplyAsCollateral() public {
    TestCaseLocalVars memory testVars;

    // deposit
    prepareUSDT(tsDepositor1);
    uint256[] memory tokenIds = prepareIsolateBAYC(tsBorrower1);

    // borrow
    prepareBorrow(tsBorrower1, address(tsBAYC), tokenIds, address(tsUSDT));

    // make some interest
    advanceTimes(365 days);

    // drop down nft price
    actionSetNftPrice(address(tsBAYC), 5000);

    // auction
    prepareAuction(tsLiquidator1, address(tsBAYC), tokenIds, address(tsUSDT));

    // end the auction
    advanceTimes(25 hours);

    uint256[] memory liquidateAmounts = new uint256[](tokenIds.length);
    testVars.loanDataBefore = getIsolateLoanData(tsCommonPoolId, address(tsBAYC), tokenIds);
    for (uint256 i = 0; i < tokenIds.length; i++) {
      testVars.totalBidAmount += testVars.loanDataBefore[i].bidAmount;
      testVars.totalBidFine += testVars.loanDataBefore[i].bidFine;
      testVars.totalRedeemAmount += testVars.loanDataBefore[i].redeemAmount;
      testVars.totalBorrowAmount += testVars.loanDataBefore[i].borrowAmount;
    }

    testVars.poolBalanceBefore = tsUSDT.balanceOf(address(tsPoolManager));
    testVars.walletBalanceBefore1 = tsUSDT.balanceOf(address(tsLiquidator1));
    testVars.walletBalanceBefore2 = tsUSDT.balanceOf(address(tsBorrower1));
    testVars.erc721BalanceBefore1 = tsBAYC.balanceOf(address(tsLiquidator1));

    // liquidate
    tsLiquidator1.isolateLiquidate(tsCommonPoolId, address(tsBAYC), tokenIds, address(tsUSDT), liquidateAmounts, true);
    testVars.txAuctionTimestamp = block.timestamp;

    // check results
    testVars.loanDataAfter = getIsolateLoanData(tsCommonPoolId, address(tsBAYC), tokenIds);
    for (uint256 i = 0; i < tokenIds.length; i++) {
      assertEq(testVars.loanDataAfter[i].bidStartTimestamp, 0, 'bidStartTimestamp');
      assertEq(testVars.loanDataAfter[i].firstBidder, address(0), 'firstBidder');
      assertEq(testVars.loanDataAfter[i].lastBidder, address(0), 'lastBidder');
      assertEq(testVars.loanDataAfter[i].bidAmount, 0, 'bidAmount');
      assertEq(testVars.loanDataAfter[i].borrowAmount, 0, 'borrowAmount');
    }

    testVars.poolBalanceAfter = tsUSDT.balanceOf(address(tsPoolManager));
    assertEq(
      testVars.poolBalanceAfter,
      testVars.poolBalanceBefore - (testVars.totalBidAmount - testVars.totalBorrowAmount),
      'tsPoolManager usdt balance'
    );

    testVars.walletBalanceAfter1 = tsUSDT.balanceOf(address(tsLiquidator1));
    assertEq(testVars.walletBalanceAfter1, testVars.walletBalanceBefore1, 'tsLiquidator1 usdt balance');

    testVars.walletBalanceAfter2 = tsUSDT.balanceOf(address(tsBorrower1));
    assertEq(
      testVars.walletBalanceAfter2,
      (testVars.walletBalanceBefore2 + (testVars.totalBidAmount - testVars.totalBorrowAmount)),
      'tsBorrower1 usdt balance'
    );

    testVars.erc721BalanceAfter1 = tsBAYC.balanceOf(address(tsLiquidator1));
    assertEq(testVars.erc721BalanceAfter1, (testVars.erc721BalanceBefore1), 'tsLiquidator1 bayc balance');
  }

  function test_Anyone_Can_LiquidateWETH() public {
    TestCaseLocalVars memory testVars;

    // deposit
    prepareWETH(tsDepositor1);
    uint256[] memory tokenIds = prepareIsolateBAYC(tsBorrower1);

    // borrow
    prepareBorrow(tsBorrower1, address(tsBAYC), tokenIds, address(tsWETH));

    // make some interest
    advanceTimes(365 days);

    // drop down nft price
    actionSetNftPrice(address(tsBAYC), 5000);

    // auction
    prepareAuction(tsLiquidator1, address(tsBAYC), tokenIds, address(tsWETH));

    // end the auction
    advanceTimes(25 hours);

    uint256[] memory liquidateAmounts = new uint256[](tokenIds.length);
    testVars.loanDataBefore = getIsolateLoanData(tsCommonPoolId, address(tsBAYC), tokenIds);
    for (uint256 i = 0; i < tokenIds.length; i++) {
      testVars.totalBidAmount += testVars.loanDataBefore[i].bidAmount;
      testVars.totalBidFine += testVars.loanDataBefore[i].bidFine;
      testVars.totalRedeemAmount += testVars.loanDataBefore[i].redeemAmount;
      testVars.totalBorrowAmount += testVars.loanDataBefore[i].borrowAmount;
    }

    testVars.poolBalanceBefore = tsWETH.balanceOf(address(tsPoolManager));
    testVars.walletBalanceBefore1 = tsWETH.balanceOf(address(tsLiquidator1));
    testVars.walletBalanceBefore2 = tsWETH.balanceOf(address(tsBorrower1));
    testVars.erc721BalanceBefore1 = tsBAYC.balanceOf(address(tsLiquidator1));

    // liquidate
    // note: check tsBorrower2 can liquidate and receive nfts without bidding.
    tsBorrower2.isolateLiquidate(tsCommonPoolId, address(tsBAYC), tokenIds, address(tsWETH), liquidateAmounts, false);
    testVars.erc721BalanceAfter1 = tsBAYC.balanceOf(address(tsBorrower2));
    assertEq(
      testVars.erc721BalanceAfter1,
      (testVars.erc721BalanceBefore1 + tokenIds.length),
      'tsLiquidator1 bayc balance'
    );

  }
  
}
