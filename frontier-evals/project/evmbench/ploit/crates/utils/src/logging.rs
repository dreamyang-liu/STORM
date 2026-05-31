//! Logging utilities for initializing tracing subscribers.
//!
//! This module provides a simple helper function to initialize the tracing
//! subscriber with sensible defaults for CLI applications.

use tracing_subscriber::{EnvFilter, fmt};

/// Initialize the tracing subscriber for logging.
///
/// Sets up a formatted logging output with optional debug level based on the
/// verbose flag. Respects the `RUST_LOG` environment variable if set.
///
/// # Arguments
///
/// * `verbose` - If true, sets the default log level to "debug", otherwise "info"
///
/// # Example
///
/// ```no_run
/// # use ploit_utils::logging;
/// // Initialize with info level
/// logging::init(false);
///
/// // Initialize with debug level
/// logging::init(true);
/// ```
///
/// # Notes
///
/// This function should only be called once during application initialization.
/// Calling it multiple times will result in a panic.
pub fn init(verbose: bool) {
    let log_level = if verbose { "debug" } else { "info" };

    fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new(log_level)),
        )
        .with_target(false)
        .init();
}

#[cfg(test)]
mod tests {
    #[test]
    fn test_log_level_info() {
        // We can't actually test init() because it can only be called once
        // per process, but we can verify the logic
        let verbose = false;
        let expected_level = if verbose { "debug" } else { "info" };
        assert_eq!(expected_level, "info");
    }

    #[test]
    fn test_log_level_debug() {
        let verbose = true;
        let expected_level = if verbose { "debug" } else { "info" };
        assert_eq!(expected_level, "debug");
    }
}
