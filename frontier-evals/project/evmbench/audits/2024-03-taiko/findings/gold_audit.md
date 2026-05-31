# 2024-03-taiko Report

## [H-01] Gas issuance is inflated and will halt the chain or lead to incorrect base fee

*Submitted by monrel*

[https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L2/TaikoL2.sol#L140-L143](https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L2/TaikoL2.sol#L140-L143)

[https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L2/TaikoL2.sol#L262-L293](https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L2/TaikoL2.sol#L262-L293)

[https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L2/TaikoL2.sol#L145-L152](https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L2/TaikoL2.sol#L145-L152)

[https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L2/TaikoL2.sol#L140-L143](https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L2/TaikoL2.sol#L140-L143)

The base fee calculation in the `anchor()` function is incorrect. Issuance is over inflated and will either lead to the chain halting or a severely deflated base fee.

We calculate the 1559 base fee and compare it to `block.basefee` [https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L2/TaikoL2.sol#L140-L143](https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L2/TaikoL2.sol#L140-L143)

```
        (basefee, gasExcess) = _calc1559BaseFee(config, _l1BlockId, _parentGasUsed);
        if (!skipFeeCheck() && block.basefee != basefee) {
            revert L2_BASEFEE_MISMATCH();
        
```

But the calculation is incorrect:

[https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L2/TaikoL2.sol#L262-L293](https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L2/TaikoL2.sol#L262-L293)

```
        if (gasExcess > 0) {
            // We always add the gas used by parent block to the gas excess
            // value as this has already happened
            uint256 excess = uint256(gasExcess) + _parentGasUsed;

            // Calculate how much more gas to issue to offset gas excess.
            // after each L1 block time, config.gasTarget more gas is issued,
            // the gas excess will be reduced accordingly.
            // Note that when lastSyncedBlock is zero, we skip this step
            // because that means this is the first time calculating the basefee
            // and the difference between the L1 height would be extremely big,
            // reverting the initial gas excess value back to 0.
            uint256 numL1Blocks;
            if (lastSyncedBlock > 0 && _l1BlockId > lastSyncedBlock) {
                numL1Blocks = _l1BlockId - lastSyncedBlock;
            }

            if (numL1Blocks > 0) {
                uint256 issuance = numL1Blocks * _config.gasTargetPerL1Block;
                excess = excess > issuance ? excess - issuance : 1;
            }

            gasExcess_ = uint64(excess.min(type(uint64).max));

            // The base fee per gas used by this block is the spot price at the
            // bonding curve, regardless the actual amount of gas used by this
            // block, however, this block's gas used will affect the next
            // block's base fee.
            basefee_ = Lib1559Math.basefee(
                gasExcess_, uint256(_config.basefeeAdjustmentQuotient) * _config.gasTargetPerL1Block
            );
        }
```

Instead of issuing `_config.gasTargetPerL1Block` for each L1 block we end up issuing `uint256 issuance = (_l1BlockOd - lastSyncedBlock) * _config.gasTargetPerL1Block` .

`lastSyncedBlock` is only updated every 5 blocks.

[https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L2/TaikoL2.sol#L145-L152](https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L2/TaikoL2.sol#L145-L152)

```
        if (_l1BlockId > lastSyncedBlock + BLOCK_SYNC_THRESHOLD) {
            // Store the L1's state root as a signal to the local signal service to
            // allow for multi-hop bridging.
            ISignalService(resolve("signal_service", false)).syncChainData(
                ownerChainId, LibSignals.STATE_ROOT, _l1BlockId, _l1StateRoot
            );
            lastSyncedBlock = _l1BlockId;
        }
```

If `anchor()` is called on 5 consecutive blocks we end up issuing
in total `15 * _config.gasTargetPerL1Block` instead of `5 * _config.gasTargetPerL1Block` .

When the calculated base fee is compared to the `block.basefee` the following happens:

- If block.basefeereports the correct base fee this will end up halting the chain since they will not match.
- If block.basefee is using the same flawed calculation the chain continues but with a severely reduced and incorrect base fee.

Here is a simple POC showing the actual issuance compared to the expected issuance. Paste the code into TaikoL1LibProvingWithTiers.t.sol and run `forge test --match-test testIssuance -vv` .

Foundry, VScode

Issue exactly `config.gasTargetPerL1Block` for each L1 block.

**dantaik (Taiko) confirmed and commented:**

> This is a valid bug report. Fixed in this PR: https://github.com/taikoxyz/taiko-mono/pull/16543

**0xean (Judge) commented:**

> I don’t see a direct loss of funds here and believe M is the correct severity.
> 2 — Med: Assets not at direct risk, but the function of the protocol or its availability could be impacted, or leak value with a hypothetical attack path with stated assumptions, but external requirements.
> 3 — High: Assets can be stolen/lost/compromised directly (or indirectly if there is a valid attack path that does not have hand-wavy hypotheticals).

**0xmonrel (Warden) commented:**

> A halted chain leads to frozen funds. The chain will progress for a minimum of 2 blocks since the calculation is correct when lastSyncedBlock =0 and when _l1BlockID-lastSyncedBlock=1
> After the second block the base fee will still be correct as long as excess < issuance for both the inflated and correct calculating since both result in excess=1
> https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L2/TaikoL2.sol#L279-L282
>             if (numL1Blocks > 0) {
>                 uint256 issuance = numL1Blocks * _config.gasTargetPerL1Block;
>                 excess = excess > issuance ? excess - issuance : 1;
>             }
> At the block where the base fee is incorrect the chain is halted and funds are locked since the anchor now reverts in perpetuity.
> In practice Taiko can easily release all funds by upgrading the contracts but I believe such an intervention should not be considered when evaluating the severity of an issue. From C4 Supreme Court session, Fall 2023
> Contract upgradability should never be used as a severity mitigation, i.e. we assume contracts are non-upgradable.
> I therefore believe a High is fair here.

**0xean (Judge) commented:**

> I don’t entirely agree since the chain would be halted so soon in its existence, that being said, some amount of funds, albeit small, would likely be lost.  @dantaik / @adaki2004 any last comments before leaving as H severity?

**adaki2004 (Taiko) commented:**

> Agreed, can do!

**0xean (Judge) commented:**

> Awarding as H, final decision.

## [H-02] Validity and contests bond ca be incorrectly burned for the correct and ultimately verified transition

*Submitted by monrel, also found by t0x1c*

[https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L1/libs/LibProving.sol#L387-L392](https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L1/libs/LibProving.sol#L387-L392)

[https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L1/libs/LibProving.sol#L189-L199](https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L1/libs/LibProving.sol#L189-L199)

[https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L1/libs/LibVerifying.sol#L178-L189](https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L1/libs/LibVerifying.sol#L178-L189)

Both validity and contests bonds can be wrongfully slashed even if the transition ends up being the correct and verified one.

The issue comes from the fact that the history of the final verified transition is not taken into account.

Example 1: Validity bond is wrongfully burned:

1. Bob Proves transition T1 for parent P1
2. Alice contests and proves T2 for parent P1 with higher tier proof.
3. Guardians steps in to correctly prove T1 for parent P2.

At step 2 Bob loses his bond and is permanentley written out of the history of P1 [https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L1/libs/LibProving.sol#L387-L392](https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L1/libs/LibProving.sol#L387-L392)

```
    _ts.validityBond = _tier.validityBond; 
    _ts.contestBond = 1; 
    _ts.contester = address(0);
    _ts.prover = msg.sender;
    _ts.tier = _proof.tier; 
```

Example 2: Contest bond wrongfully slashed:

1. Alice proves T1 for parent P1 with SGX
2. Bob contests T1 for parent P1
3. Alice proves T1 with SGX_ZK parent P1
4. Guardian steps in to correctly disprove T1 with T2 for parent P1

Bob was correct and T1 was ultimately proven false. Bob still loses his contest bond.

When the guardian overrides the proof they can not pay back Bob’s validity or contesting bond. They are only able to pay back a liveness bond [https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L1/libs/LibProving.sol#L189-L199](https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L1/libs/LibProving.sol#L189-L199)

```
if (isTopTier) { 
	// A special return value from the top tier prover can signal this
	// contract to return all liveness bond.
	bool returnLivenessBond = blk.livenessBond > 0 && _proof.data.length == 32
		&& bytes32(_proof.data) == RETURN_LIVENESS_BOND;

	if (returnLivenessBond) {
		tko.transfer(blk.assignedProver, blk.livenessBond);
		blk.livenessBond = 0;
	} 
}
```

These funds are now frozen since they are sent to the Guardian contract which has no ability to recover them.

[https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L1/libs/LibVerifying.sol#L178-L189](https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L1/libs/LibVerifying.sol#L178-L189)

```
                uint256 bondToReturn = uint256(ts.validityBond) + blk.livenessBond;

                if (ts.prover != blk.assignedProver) {
                    bondToReturn -= blk.livenessBond >> 1;
                }

                IERC20 tko = IERC20(_resolver.resolve("taiko_token", false));
                tko.transfer(ts.prover, bondToReturn)
```

`ts.prover` will be the Guardian since they are the last to prove the block

POC for example 1. Paste the below code into the `TaikoL1LibProvingWithTiers.t` file and run `forge test --match-test testProverLoss -vv`

Foundry, VScode

The simplest solution is to allow the guardian to pay back validity and contest bonds in the same manner as for liveness bonds. This keeps the simple design while allowing bonds to be recovered if a prover or contesters action is ultimately proven correct.

Guardian will pass in data in `_proof.data` that specifies the address, tiers and bond type that should be refunded. Given that Guardians already can verify any proof this does not increase centralization.

We also need to not to not recover any reward when we prove with Guardian and `_overrideWithHigherProof()` is called. If the `ts.validityBond` reward is sent to the Guardian it will be locked. Instead we need to keep it in TaikoL1 such that it can be recovered as described above

```
+if (_tier.contestBond != 0){
	unchecked {
		if (reward > _tier.validityBond) {
			_tko.transfer(msg.sender, reward - _tier.validityBond);
		} else {
			_tko.transferFrom(msg.sender, address(this), _tier.validityBond - reward);
		}
	}
+}
```

**dantaik (Taiko) commented:**

> This is a valid report but we knew this “flaw” and the current behavior is by design.
> The odd that a valid transition is proven, then contested and overwritten by another proof, then proven again with even a higher tier should be rare, if this happens even once, we should know the second prover is buggy and shall change the tier configuration to remove it.
> For provers who suffer a loss due to such prover bugs, Taiko foundation may send them compensation to cover there loss. We do not want to handle cover-your-loss payment in the protocol.

**adaki2004 (Taiko) confirmed, but disagreed with severity and commented:**

> This is an attack on the tier system, right ? But the economical disincentives doing so shall be granted by the bonds - not to challenge proofs which we do know are correct, just to make someone lose money as there is no advantage. The challenger would lose even more money - and the correct prover would be refunded by Taiko Foundation.
> Severity: medium, (just as: https://github.com/code-423n4/2024-03-taiko-findings/issues/227)

**0xean (Judge) commented:**

> I am going to leave as H, I think there is a direct loss of funds here.  
> This comment:
> The challenger would lose even more money 
> Makes me second guess that slightly, but still think H is correct.

## [H-03] Users will never be able to withdraw their claimed airdrop fully in ERC20Airdrop2.sol contract

*Submitted by MrPotatoMagic, also found by Aymen0909, alexfilippov314, pa6kuda, and t4sk*

**Context:** The ERC20Airdrop2.sol contract is for managing Taiko token airdrop for eligible users, but the withdrawal is not immediate and is subject to a withdrawal window.

Users can claim their tokens within claimStart and claimEnd. Once the claim window is over at claimEnd, they can withdraw their tokens between claimEnd and claimEnd + withdrawalWindow. During this withdrawal period, the tokens unlock linearly i.e. the tokens only become fully withdrawable at claimEnd + withdrawalWindow.

**Issue:** The issue is that once the tokens for a user are fully unlocked, the [withdraw()](https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/team/airdrop/ERC20Airdrop2.sol#L88) function cannot be called anymore due to the [ongoingWithdrawals modifier](https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/team/airdrop/ERC20Airdrop2.sol#L39) having a strict `claimEnd + withdrawalWindow < block.timestamp` check in its second condition.

**Impact:** Although the tokens become fully unlocked when block.timestamp = claimEnd + withdrawalWindow, it is extremely difficult or close to impossible for normal users to time this to get their full allocated claim amount. This means that users are always bound to lose certain amount of their eligible claim amount. This lost amount can be small for users who claim closer to claimEnd + withdrawalWindow and higher for those who partially claimed initially or did not claim at all thinking that they would claim once their tokens are fully unlocked.

How to use this POC:

- Add the POC to test/team/airdrop/ERC20Airdrop2.t.sol
- Run the POC using forge test --match-test testAirdropIssue -vvv
- The POC demonstrates how alice was only able to claim half her tokens out of her total 100 tokens claimable amount.

```
      function testAirdropIssue() public {
        vm.warp(uint64(block.timestamp + 11));

        vm.prank(Alice, Alice);
        airdrop2.claim(Alice, 100, merkleProof);

        // Roll 5 days after
        vm.roll(block.number + 200);
        vm.warp(claimEnd + 5 days);

        airdrop2.withdraw(Alice);

        console.log("Alice balance:", token.balanceOf(Alice));

        // Roll 6 days after
        vm.roll(block.number + 200);
        vm.warp(claimEnd + 11 days);

        vm.expectRevert(ERC20Airdrop2.WITHDRAWALS_NOT_ONGOING.selector);
        airdrop2.withdraw(Alice);
    }
```

```
Logs:
  > MockERC20Airdrop @ 0x0000000000000000000000000000000000000000
    proxy      : 0xF62849F9A0B5Bf2913b396098F7c7019b51A820a
    impl       : 0x2e234DAe75C793f67A35089C9d99245E1C58470b
    owner      : 0x7FA9385bE102ac3EAc297483Dd6233D62b3e1496
    msg.sender : 0x1804c8AB1F12E6bbf3894d4083f33e07309d1f38
    this       : 0x7FA9385bE102ac3EAc297483Dd6233D62b3e1496
  Alice balance: 50
```

In the [modifier ongoingWithdrawals()](https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/team/airdrop/ERC20Airdrop2.sol#L39) , consider adding a buffer window in the second condition that gives users enough time to claim the fully unlocked tokens.

```
    uint256 constant bufferWindow = X mins/hours/days;

    modifier ongoingWithdrawals() {
        if (claimEnd > block.timestamp || claimEnd + withdrawalWindow < block.timestamp + bufferWindow) {
            revert WITHDRAWALS_NOT_ONGOING();
        }
        _;
    }
```

**dantaik (Taiko) commented:**

> Fixed in https://github.com/taikoxyz/taiko-mono/pull/16596

**adaki2004 (Taiko) confirmed and commented:**

> It is indeed a bug in the flow, while we removed Airdrop2, it is still a confirmed finding on the repo for auditing.

## [H-04] Taiko L1 - Proposer can maliciously cause loss of funds by forcing someone else to pay prover’s fee

*Submitted by zzebra83, also found by MrPotatoMagic, monrel, mojito_auditor, and ladboy233*

[https://github.com/code-423n4/2024-03-taiko/blob/0d081a40e0b9637eddf8e760fabbecc250f23599/packages/protocol/contracts/L1/hooks/AssignmentHook.sol#L113-L116](https://github.com/code-423n4/2024-03-taiko/blob/0d081a40e0b9637eddf8e760fabbecc250f23599/packages/protocol/contracts/L1/hooks/AssignmentHook.sol#L113-L116)

[https://github.com/code-423n4/2024-03-taiko/blob/0d081a40e0b9637eddf8e760fabbecc250f23599/packages/protocol/contracts/L1/libs/LibProposing.sol#L85-L87](https://github.com/code-423n4/2024-03-taiko/blob/0d081a40e0b9637eddf8e760fabbecc250f23599/packages/protocol/contracts/L1/libs/LibProposing.sol#L85-L87)

[https://github.com/code-423n4/2024-03-taiko/blob/0d081a40e0b9637eddf8e760fabbecc250f23599/packages/protocol/contracts/L1/libs/LibProposing.sol#L249-L255](https://github.com/code-423n4/2024-03-taiko/blob/0d081a40e0b9637eddf8e760fabbecc250f23599/packages/protocol/contracts/L1/libs/LibProposing.sol#L249-L255)

Proposal of new blocks triggers a call to proposeBlock in the libProposing library. In that function, there is this the following block of code:

```
        if (params.coinbase == address(0)) {
        params.coinbase = msg.sender;
    }
```

This sets the params.coinbase variable set by the caller of the function to be the msg.sender if it was empty.

As part of the process of proposal, hooks can be called of type AssignmentHook. An assignment hook’s onBlockProposed will be triggered as follows:

```
                // When a hook is called, all ether in this contract will be send to the hook.
            // If the ether sent to the hook is not used entirely, the hook shall send the Ether
            // back to this contract for the next hook to use.
            // Proposers shall choose use extra hooks wisely.
            IHook(params.hookCalls[i].hook).onBlockProposed{ value: address(this).balance }(
                blk, meta_, params.hookCalls[i].data
            );
```

Notice how the meta data is passed to this function. Part of the function of the onBlockProposed is to pay the assigned prover their fee and the payee should be the current proposer of the block. this is done as follows:

```
        // The proposer irrevocably pays a fee to the assigned prover, either in
    // Ether or ERC20 tokens.
    if (assignment.feeToken == address(0)) {
        // Paying Ether
        _blk.assignedProver.sendEther(proverFee, MAX_GAS_PAYING_PROVER);
    } else {
        // Paying ERC20 tokens
        IERC20(assignment.feeToken).safeTransferFrom(
            _meta.coinbase, _blk.assignedProver, proverFee
        );
    }
```

Notice how if the payment is in ERC20 tokens, the payee will be the variable  _meta.coinbase, and like we showed earlier, this can be set to any arbitrary address by the proposer. This can lead to a scenario as such:

1. proposer A approves the assignmentHook contract to spend a portion of their tokens, the allowance is set higher than the actual fee they will be paying.
2. proposer A proposes a block, and a fee is charged and payed to the assigned prover, but there remains allowance that the assignment hook contract can still use.
3. proposer B proposes a block and sets params.coinbase as the the address of proposer A.
4. proposer A address will be the payee of the fee for the assigned prover for the block proposed by proposer B.

The scenario above describes how someone can be forced maliciously to pay fees for block proposals by other actors.

A simple fix to this to ensure the block proposer will always be the msg.sender, as such:

```
    if (params.coinbase == address(0 || params.coinbase != msg.sender)) {
        params.coinbase = msg.sender;
    }
```

**dantaik (Taiko) confirmed and commented:**

> This is a valid bug report. It has been fixed here: https://github.com/taikoxyz/taiko-mono/pull/16327

## [H-05] Signatures can be replayed in withdraw() to withdraw more tokens than the user originally intended.

*Submitted by lightoasis, also found by 0xleadwizard, wangxx2026, alexfilippov314, ladboy233, and Tendency*

Signatures can be replayed in `withdraw()` to withdraw more tokens than the user originally intended.

In the TimelockTokenPool.sol contracts, users can provide a signature to allow someone else to withdraw all their withdrawable tokens on their behalf using their signature. [TimelockTokenPool.sol#L170)](https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/team/TimelockTokenPool.sol#L170)

```
    function withdraw(address _to, bytes memory _sig) external {
        if (_to == address(0)) revert INVALID_PARAM();
        bytes32 hash = keccak256(abi.encodePacked("Withdraw unlocked Taiko token to: ", _to));
 @>     address recipient = ECDSA.recover(hash, _sig);
        _withdraw(recipient, _to);
    }
```

As seen from above, the signature provided does not include a nonce and this can lead to signature replay attacks. Due to the lack of a nonce,  withdraw() can be called multiple times with the same signature. Therefore, if a user provides a signature to withdraw all his withdrawable tokens at one particular time, an attacker can repeatedly call withdraw() with the same signature to withdraw more tokens than the user originally intended.
The vulnerability is similar to [Arbitrum H-01](https://solodit.xyz/issues/h-01-signatures-can-be-replayed-in-castvotewithreasonandparamsbysig-to-use-up-more-votes-than-a-user-intended-code4rena-arbitrum-foundation-arbitrum-foundation-git) where  user’s signatures could be replayed to use up more votes than a user intended due to a lack of nonce.

Consider using a nonce or other signature replay protection in the TimelockTokenPool contract.

**dantaik (Taiko) confirmed and commented:**

> Valid bug report, trying to fix it in this PR: https://github.com/taikoxyz/taiko-mono/pull/16611/files
