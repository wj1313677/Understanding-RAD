import { useState, useEffect } from 'react'
import './App.css'
import CesiumViewer from './components/CesiumViewer'
import DeckGLViewer from './components/DeckGLViewer'
import { loadFRAData } from './data/dataLoader'

function App() {
  const [data, setData] = useState([]);
  const [viewMode, setViewMode] = useState('cesium'); // 'cesium' or 'deckgl'
  const [theme, setTheme] = useState('dark'); // 'dark' or 'light'
  const [loading, setLoading] = useState(true);
  const [searchText, setSearchText] = useState('');
  const [highlightedPoints, setHighlightedPoints] = useState(null); // null means no filter

  useEffect(() => {
    loadFRAData().then(points => {
      setData(points);
      setLoading(false);
      console.log("Loaded points:", points.length);
    });
  }, []);

  // Search Logic
  useEffect(() => {
    if (!searchText.trim()) {
      setHighlightedPoints(null);
      return;
    }

    const terms = searchText.split(',').map(s => s.trim().toUpperCase()).filter(s => s);
    if (terms.length === 0) {
      setHighlightedPoints(null);
      return;
    }

    const matches = new Set();
    // Optimize: Create a map or just iterate if data small? Data is ~11k points? Iteration fine.
    // Filter points that match any term
    data.forEach(p => {
      if (terms.includes(p.name)) {
        matches.add(p.name);
      }
    });
    setHighlightedPoints(matches);
  }, [searchText, data]);

  return (
    <div style={{ position: 'relative', width: '100vw', height: '100vh', overflow: 'hidden' }}>
      {/* UI Controls */}
      <div style={{
        position: 'absolute',
        top: 20,
        left: 20,
        zIndex: 1000,
        background: 'rgba(255, 255, 255, 0.9)',
        padding: '15px',
        borderRadius: '8px',
        boxShadow: '0 2px 10px rgba(0,0,0,0.3)',
        maxHeight: '90vh',
        overflowY: 'auto'
      }}>
        <h2 style={{ margin: '0 0 10px 0' }}>FRA Points Comparison</h2>

        {/* Search Input */}
        <div style={{ marginBottom: '15px' }}>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>Search Points:</label>
          <input
            type="text"
            placeholder="e.g. KOMIB, BITLA"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{
              width: '100%',
              padding: '8px',
              boxSizing: 'border-box',
              borderRadius: '4px',
              border: '1px solid #ccc'
            }}
          />
          <div style={{ fontSize: '11px', color: '#666', marginTop: '2px' }}>
            Comma-separated list (e.g. "KOMIB, BITLA")
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
          <button
            onClick={() => setViewMode('cesium')}
            style={{
              fontWeight: viewMode === 'cesium' ? 'bold' : 'normal',
              backgroundColor: viewMode === 'cesium' ? '#007bff' : '#eee',
              color: viewMode === 'cesium' ? '#fff' : '#000',
              border: 'none',
              padding: '8px 16px',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            CesiumJS
          </button>
          <button
            onClick={() => setViewMode('deckgl')}
            style={{
              fontWeight: viewMode === 'deckgl' ? 'bold' : 'normal',
              backgroundColor: viewMode === 'deckgl' ? '#007bff' : '#eee',
              color: viewMode === 'deckgl' ? '#fff' : '#000',
              border: 'none',
              padding: '8px 16px',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Deck.gl
          </button>
        </div>

        <div style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
          <button
            onClick={() => setTheme('dark')}
            style={{
              fontWeight: theme === 'dark' ? 'bold' : 'normal',
              backgroundColor: theme === 'dark' ? '#333' : '#eee',
              color: theme === 'dark' ? '#fff' : '#000',
              border: 'none',
              padding: '8px 16px',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Dark Map
          </button>
          <button
            onClick={() => setTheme('light')}
            style={{
              fontWeight: theme === 'light' ? 'bold' : 'normal',
              backgroundColor: theme === 'light' ? '#ddd' : '#eee',
              color: theme === 'light' ? '#000' : '#888',
              border: 'none',
              padding: '8px 16px',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Light Map
          </button>
        </div>
        <div>
          {loading ? 'Loading data...' : `${data.length} points loaded`}
          {highlightedPoints && (
            <div style={{ marginTop: '5px', color: '#007bff', fontWeight: 'bold' }}>
              {highlightedPoints.size} found
            </div>
          )}
        </div>
      </div>

      {/* Main View */}
      {viewMode === 'cesium' ? (
        <CesiumViewer data={data} theme={theme} highlightedPoints={highlightedPoints} />
      ) : (
        <DeckGLViewer data={data} theme={theme} highlightedPoints={highlightedPoints} />
      )}
    </div>
  )
}

export default App
