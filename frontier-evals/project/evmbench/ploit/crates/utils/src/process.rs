//! Process utilities for killing processes by port.
//!
//! This module provides platform-specific functionality to find and kill
//! processes occupying specific ports. Works on macOS, Windows, and Linux.

use anyhow::{Context, Result};
use std::process::Command;

/// Kill a process occupying the specified port
///
/// Uses platform-specific commands to find and terminate the process.
///
/// # Arguments
///
/// * `port` - The port number to kill the process on
///
/// # Returns
///
/// Returns `Ok(())` on success or if no process is found, or an error if the operation fails.
///
/// # Examples
///
/// ```no_run
/// use ploit_utils::process::kill_port;
///
/// # fn main() -> anyhow::Result<()> {
/// kill_port(8545)?;
/// # Ok(())
/// # }
/// ```
pub fn kill_port(port: u16) -> Result<()> {
    #[cfg(target_os = "macos")]
    {
        kill_process_macos(port)
    }

    #[cfg(target_os = "windows")]
    {
        kill_process_windows(port)
    }

    #[cfg(not(any(target_os = "macos", target_os = "windows")))]
    {
        kill_process_linux(port)
    }
}

/// Kill process on macOS using lsof and kill
#[cfg(target_os = "macos")]
fn kill_process_macos(port: u16) -> Result<()> {
    debug!("Using macOS lsof command to find and kill process");

    // Find the PID using lsof
    let lsof_output = Command::new("lsof")
        .args(["-ti", &format!(":{}", port)])
        .output()
        .context("Failed to execute lsof command")?;

    let pid_str = String::from_utf8_lossy(&lsof_output.stdout);
    let pid = pid_str.trim();

    if !lsof_output.status.success() || pid.is_empty() {
        info!("No process found on port {}", port);
        return Ok(());
    }

    debug!("Found PID: {}", pid);

    // Kill the process
    let kill_output = Command::new("kill")
        .args(["-9", pid])
        .output()
        .context("Failed to execute kill command")?;

    if !kill_output.status.success() {
        let stderr = String::from_utf8_lossy(&kill_output.stderr);
        anyhow::bail!("Failed to kill process {}: {}", pid, stderr);
    }

    info!("Killed process {} on port {}", pid, port);
    Ok(())
}

/// Kill process on Windows using PowerShell and taskkill
#[cfg(target_os = "windows")]
fn kill_process_windows(port: u16) -> Result<()> {
    debug!("Using Windows PowerShell to find and kill process");

    // Use PowerShell to find the PID
    let ps_command = format!(
        "$process = Get-NetTCPConnection -LocalPort {} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess; if ($process) {{ Write-Output $process }} else {{ exit 1 }}",
        port
    );

    let ps_output = Command::new("powershell")
        .args(["-NoProfile", "-Command", &ps_command])
        .output()
        .context("Failed to execute PowerShell command")?;

    let pid_str = String::from_utf8_lossy(&ps_output.stdout);
    let pid = pid_str.trim();

    if !ps_output.status.success() || pid.is_empty() {
        info!("No process found on port {}", port);
        return Ok(());
    }

    debug!("Found PID: {}", pid);

    // Kill the process using taskkill
    let kill_output = Command::new("taskkill")
        .args(["/PID", pid, "/F"])
        .output()
        .context("Failed to execute taskkill command")?;

    if !kill_output.status.success() {
        let stderr = String::from_utf8_lossy(&kill_output.stderr);
        anyhow::bail!("Failed to kill process {}: {}", pid, stderr);
    }

    info!("Killed process {} on port {}", pid, port);
    Ok(())
}

/// Kill process on Linux using lsof and kill
#[cfg(not(any(target_os = "macos", target_os = "windows")))]
fn kill_process_linux(port: u16) -> Result<()> {
    debug!("Using Linux lsof command to find and kill process");

    // Find the PID using lsof
    let lsof_output = Command::new("lsof")
        .args(["-ti", &format!(":{}", port)])
        .output()
        .context("Failed to execute lsof command")?;

    let pid_str = String::from_utf8_lossy(&lsof_output.stdout);
    let pid = pid_str.trim();

    if !lsof_output.status.success() || pid.is_empty() {
        info!("No process found on port {}", port);
        return Ok(());
    }

    debug!("Found PID: {}", pid);

    // Kill the process
    let kill_output = Command::new("kill")
        .args(["-9", pid])
        .output()
        .context("Failed to execute kill command")?;

    if !kill_output.status.success() {
        let stderr = String::from_utf8_lossy(&kill_output.stderr);
        anyhow::bail!("Failed to kill process {}: {}", pid, stderr);
    }

    info!("Killed process {} on port {}", pid, port);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_kill_port_nonexistent() {
        // Test that killing a port with no process doesn't error
        // Using a high port number that's unlikely to be in use
        let result = kill_port(65432);
        assert!(result.is_ok());
    }
}
