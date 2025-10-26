def pytest_configure(config):
    # If pytest-cov is active, enforce 85% coverage minimum.
    if config.pluginmanager.hasplugin('pytest_cov'):
        cov_plugin = config.pluginmanager.getplugin('_cov')
        # Set fail-under dynamically if not provided via CLI
        if cov_plugin is not None and not hasattr(config.option, 'cov_fail_under'):
            config.option.cov_fail_under = 85 