import { Routes, Route, Link } from 'react-router-dom';
import './App.css';
import Downloader from './pages/Downloader';
import Library from './pages/Library';
import { Youtube, Download, Library as LibraryIcon } from 'lucide-react';

function App() {
  return (
    <div className="app-layout">
      <nav className="sidebar">
        <div className="logo">
          <Youtube color="red" size={32} />
          <h2>YT Suite</h2>
        </div>
        <ul className="nav-links">
          <li>
            <Link to="/download">
              <Download size={20} />
              <span>Downloader</span>
            </Link>
          </li>
          <li>
            <Link to="/library">
              <LibraryIcon size={20} />
              <span>Library</span>
            </Link>
          </li>
        </ul>
      </nav>
      <main className="content">
        <Routes>
          <Route path="/" element={<Downloader />} />
          <Route path="/download" element={<Downloader />} />
          <Route path="/library" element={<Library />} />
        </Routes>
      </main>
    </div>
  );
}

export default App
