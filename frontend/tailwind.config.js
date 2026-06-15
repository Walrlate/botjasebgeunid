/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        'geun-bg': '#F1F5F9',         // Telegram-like light grayish blue background
        'geun-surface': '#FFFFFF',    // Frost white card background
        'geun-blue': '#2481CC',       // Official Telegram Blue primary
        'geun-purple': '#4A90E2',     // Royal Indigo secondary (GeunID unique identity)
        'geun-dark': '#0F172A',       // Slate 900 for premium dark text
        'geun-muted': '#64748B',      // Slate 500 for descriptive texts
        'geun-border': 'rgba(36, 129, 204, 0.08)',
      },
      backgroundImage: {
        'geun-gradient': 'linear-gradient(135deg, #2481CC 0%, #4A90E2 100%)',
      },
      boxShadow: {
        'soft': '0 8px 30px rgba(0, 0, 0, 0.02)',
        'premium': '0 12px 40px rgba(36, 129, 204, 0.08)',
        'active-glow': '0 0 20px rgba(36, 129, 204, 0.15)',
      }
    },
  },
  plugins: [],
};
