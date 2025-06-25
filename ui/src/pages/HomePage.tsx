import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { parseReferences } from '../services/api';
import useStore from '../store';

const HomePage: React.FC = () => {
  const [url, setUrl] = useState('');
  const navigate = useNavigate();
  const setJobId = useStore(s => s.setParseJobId);

  const mutation = useMutation({
    mutationFn: parseReferences,
    onSuccess: data => {
      setJobId(data.job_id);
      navigate('/references');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (url) mutation.mutate(url);
  };

  return (
    <div className="max-w-xl mx-auto">
      <h2 className="text-2xl font-semibold mb-4">Parse Wikipedia References</h2>
      <form onSubmit={handleSubmit} className="flex items-center space-x-2">
        <input
          type="url"
          required
          value={url}
          onChange={e => setUrl(e.target.value)}
          placeholder="https://en.wikipedia.org/wiki/Large_language_model"
          className="flex-1 p-2 border rounded-md"
        />
        <button
          type="submit"
          className="px-4 py-2 bg-primary text-white rounded hover:bg-blue-700 disabled:opacity-50"
          disabled={mutation.isLoading}
        >
          {mutation.isLoading ? 'Parsing…' : 'Parse'}
        </button>
      </form>
      {mutation.isError && (
        <p className="text-error mt-2">Error: {(mutation.error as Error).message}</p>
      )}
    </div>
  );
};

export default HomePage; 