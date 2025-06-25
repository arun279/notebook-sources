import React from 'react';

interface Props {
  percent: number;
}

const ProgressModal: React.FC<Props> = ({ percent }) => {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 p-6 rounded shadow-lg w-80 text-center">
        <h3 className="text-lg font-medium mb-4">Parsing References</h3>
        <div className="w-full bg-gray-200 rounded-full h-3 mb-4">
          <div className="bg-primary h-3 rounded-full" style={{ width: `${percent}%` }} />
        </div>
        <p>{percent.toFixed(0)} %</p>
      </div>
    </div>
  );
};

export default ProgressModal; 