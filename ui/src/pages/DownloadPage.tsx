import React from 'react';
import { downloadZipAll } from '../services/api';

const DownloadPage: React.FC = () => {
  return (
    <div className="max-w-xl mx-auto">
      <h2 className="text-2xl font-semibold mb-4">Download Center</h2>
      <button
        className="px-4 py-2 bg-primary text-white rounded"
        onClick={downloadZipAll}
      >
        Download all PDFs as ZIP
      </button>
    </div>
  );
};

export default DownloadPage; 