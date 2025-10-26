import React from 'react';
import useTheme from '../hooks/useTheme';

const ThemeToggle: React.FC = () => {
  const [theme, toggle] = useTheme();
  return (
    <button
      onClick={toggle}
      className="p-2 rounded hover:bg-white/20"
      aria-label="Toggle dark mode"
    >
      {theme === 'light' ? '🌙' : '☀️'}
    </button>
  );
};

export default ThemeToggle; 