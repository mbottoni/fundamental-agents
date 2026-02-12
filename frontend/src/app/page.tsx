import Link from 'next/link';

export default function Home() {
  return (
    <div className="bg-gray-900 text-white min-h-screen flex flex-col">
      <main className="flex-grow flex flex-col items-center justify-center p-4 text-center">
        <h1 className="text-5xl md:text-6xl font-bold mb-4">
          AI-Powered Stock Analysis
        </h1>
        <p className="text-lg md:text-xl text-gray-400 mb-8 max-w-2xl mx-auto">
          Leverage institutional-grade insights with our multi-agent AI platform.
          Get comprehensive fundamental analysis and make data-driven investment
          decisions.
        </p>
        <Link
          href="/dashboard"
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-8 rounded-lg text-lg transition duration-300"
        >
          Get Started
        </Link>
      </main>

      <footer className="p-4 text-center text-gray-500">
        <p>&copy; {new Date().getFullYear()} Stock Analyzer AI. All Rights Reserved.</p>
      </footer>
    </div>
  );
}
