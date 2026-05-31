// SPDX-License-Identifier: BUSL-1.1
pragma solidity ^0.8.0;

import {Constants} from 'src/libraries/helpers/Constants.sol';

import 'test/setup/TestWithPrepare.sol';
import '@forge-std/Test.sol';

contract YieldEthStakingEtherfi is TestWithPrepare {
  struct YieldTestVars {
    uint32 poolId;
    uint8 state;
    uint256 debtAmount;
    uint256 yieldAmount;
    uint256 unstakeFine;
    uint256 withdrawAmount;
    uint256 withdrawReqId;
  }

  function onSetUp() public virtual override {
    super.onSetUp();

    initCommonPools();

    initYieldEthStaking();
  }

  function test_Should_stake() public {
    YieldTestVars memory testVars;

    prepareWETH(tsDepositor1);

    uint256[] memory tokenIds = prepareIsolateBAYC(tsBorrower1);

    (, , uint256 stakeAmount) = tsYieldEthStakingEtherfi.getNftCollateralData(address(tsBAYC), tokenIds[0]);
    stakeAmount = (stakeAmount * 80) / 100;

    tsHEVM.prank(address(tsBorrower1));
    tsYieldEthStakingEtherfi.createYieldAccount(address(tsBorrower1));

    tsHEVM.prank(address(tsBorrower1));
    tsYieldEthStakingEtherfi.stake(tsCommonPoolId, address(tsBAYC), tokenIds[0], stakeAmount);

    (testVars.poolId, testVars.state, testVars.debtAmount, testVars.yieldAmount) = tsYieldEthStakingEtherfi
      .getNftStakeData(address(tsBAYC), tokenIds[0]);
    assertEq(testVars.poolId, tsCommonPoolId, 'poolId not eq');
    assertEq(testVars.state, Constants.YIELD_STATUS_ACTIVE, 'state not eq');
    assertEq(testVars.debtAmount, stakeAmount, 'debtAmount not eq');
    assertEq(testVars.yieldAmount, stakeAmount, 'yieldAmount not eq');

    uint256 debtAmount = tsYieldEthStakingEtherfi.getNftDebtInUnderlyingAsset(address(tsBAYC), tokenIds[0]);
    assertEq(debtAmount, stakeAmount, 'debtAmount not eq');

    (uint256 yieldAmount, ) = tsYieldEthStakingEtherfi.getNftYieldInUnderlyingAsset(address(tsBAYC), tokenIds[0]);
    assertEq(yieldAmount, stakeAmount, 'yieldAmount not eq');

    tsYieldEthStakingEtherfi.getNftCollateralData(address(tsBAYC), tokenIds[0]);
  }

  function test_Should_unstake() public {
    YieldTestVars memory testVars;

    prepareWETH(tsDepositor1);

    uint256[] memory tokenIds = prepareIsolateBAYC(tsBorrower1);

    uint256 stakeAmount = tsYieldEthStakingEtherfi.getNftValueInUnderlyingAsset(address(tsBAYC));
    stakeAmount = (stakeAmount * 80) / 100;

    tsHEVM.prank(address(tsBorrower1));
    address yieldAccount = tsYieldEthStakingEtherfi.createYieldAccount(address(tsBorrower1));

    tsHEVM.prank(address(tsBorrower1));
    tsYieldEthStakingEtherfi.stake(tsCommonPoolId, address(tsBAYC), tokenIds[0], stakeAmount);

    uint256 deltaAmount = (stakeAmount * 35) / 1000;
    tsEtherfiLiquidityPool.rebase{value: deltaAmount}(yieldAccount);

    (uint256 yieldAmount, ) = tsYieldEthStakingEtherfi.getNftYieldInUnderlyingAsset(address(tsBAYC), tokenIds[0]);
    testEquality(yieldAmount, (stakeAmount + deltaAmount), 'yieldAmount not eq');

    tsHEVM.prank(address(tsBorrower1));
    tsYieldEthStakingEtherfi.unstake(tsCommonPoolId, address(tsBAYC), tokenIds[0], 0);

    (testVars.poolId, testVars.state, testVars.debtAmount, testVars.yieldAmount) = tsYieldEthStakingEtherfi
      .getNftStakeData(address(tsBAYC), tokenIds[0]);
    assertEq(testVars.state, Constants.YIELD_STATUS_UNSTAKE, 'state not eq');

    (testVars.unstakeFine, testVars.withdrawAmount, testVars.withdrawReqId) = tsYieldEthStakingEtherfi
      .getNftUnstakeData(address(tsBAYC), tokenIds[0]);
    assertEq(testVars.unstakeFine, 0, 'state not eq');
    assertEq(testVars.withdrawAmount, yieldAmount, 'withdrawAmount not eq');
    assertGt(testVars.withdrawReqId, 0, 'withdrawReqId not gt');
  }

  function test_Should_repay() public {
    YieldTestVars memory testVars;

    prepareWETH(tsDepositor1);

    uint256[] memory tokenIds = prepareIsolateBAYC(tsBorrower1);

    uint256 stakeAmount = tsYieldEthStakingEtherfi.getNftValueInUnderlyingAsset(address(tsBAYC));
    stakeAmount = (stakeAmount * 80) / 100;

    tsHEVM.prank(address(tsBorrower1));
    tsYieldEthStakingEtherfi.createYieldAccount(address(tsBorrower1));

    tsHEVM.prank(address(tsBorrower1));
    tsYieldEthStakingEtherfi.stake(tsCommonPoolId, address(tsBAYC), tokenIds[0], stakeAmount);

    tsHEVM.prank(address(tsBorrower1));
    tsYieldEthStakingEtherfi.unstake(tsCommonPoolId, address(tsBAYC), tokenIds[0], 0);

    (testVars.unstakeFine, testVars.withdrawAmount, testVars.withdrawReqId) = tsYieldEthStakingEtherfi
      .getNftUnstakeData(address(tsBAYC), tokenIds[0]);
    tsEtherfiWithdrawRequestNFT.setWithdrawalStatus(testVars.withdrawReqId, true, false);

    tsHEVM.prank(address(tsBorrower1));
    tsYieldEthStakingEtherfi.repay(tsCommonPoolId, address(tsBAYC), tokenIds[0]);

    (testVars.poolId, testVars.state, testVars.debtAmount, testVars.yieldAmount) = tsYieldEthStakingEtherfi
      .getNftStakeData(address(tsBAYC), tokenIds[0]);
    assertEq(testVars.state, 0, 'state not eq');
    assertEq(testVars.debtAmount, 0, 'debtAmount not eq');
    assertEq(testVars.yieldAmount, 0, 'yieldAmount not eq');
  }

  function test_POC_Incorrect_Yield_tracking() public {
    YieldTestVars memory testVars;

    prepareWETH(tsDepositor1);

    uint256[] memory tokenIds = prepareIsolateBAYC(tsBorrower1);

    uint256 stakeAmount = tsYieldEthStakingEtherfi.getNftValueInUnderlyingAsset(address(tsBAYC));
    stakeAmount = (stakeAmount * 80) / 100;

    tsHEVM.prank(address(tsBorrower1));
    address yieldAccount = tsYieldEthStakingEtherfi.createYieldAccount(address(tsBorrower1));

    tsHEVM.prank(address(tsBorrower1));
    tsYieldEthStakingEtherfi.stake(tsCommonPoolId, address(tsBAYC), tokenIds[0], stakeAmount);

    tsHEVM.prank(address(tsBorrower1));
    tsYieldEthStakingEtherfi.stake(tsCommonPoolId, address(tsBAYC), tokenIds[1], stakeAmount);

    (testVars.poolId, testVars.state, testVars.debtAmount, testVars.yieldAmount) = tsYieldEthStakingEtherfi
      .getNftStakeData(address(tsBAYC), tokenIds[0]);
    uint256 yieldAmount0 = testVars.yieldAmount;

    (testVars.poolId, testVars.state, testVars.debtAmount, testVars.yieldAmount) = tsYieldEthStakingEtherfi
      .getNftStakeData(address(tsBAYC), tokenIds[1]);
    uint256 yieldAmount1 = testVars.yieldAmount;

    // Vulnerable behavior: identical stakes produce meaningfully different yield amounts.
    assertGt(yieldAmount0, yieldAmount1, 'yieldAmount0 should be greater');
    assertGt(yieldAmount0, (stakeAmount * 80) / 100, 'yieldAmount0 too low');
    assertGt(yieldAmount1, (stakeAmount * 80) / 100, 'yieldAmount1 too low');
    uint256 delta = yieldAmount0 - yieldAmount1;
    assertGt(delta, stakeAmount / 1000, 'yield delta too small');
  }

}
