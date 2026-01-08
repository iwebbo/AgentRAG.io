import { useState, useEffect } from 'react';
import { Plus, Trash2, Edit, FileText, Eye } from 'lucide-react';
import Layout from '../components/layout/Layout';
import Button from '../components/common/Button';
import Alert from '../components/common/Alert';
import Toggle from '../components/common/Toggle';
import api from '../services/api';

const Templates = () => {
  const [templates, setTemplates] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    content: '',
    variables: [],
    is_public: false
  });
  const [alert, setAlert] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    try {
      const response = await api.get('/api/templates/');
      setTemplates(response.data);
    } catch (error) {
      showAlert('error', 'Failed to load templates');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Extract variables from content ({{variable}})
      const variableMatches = formData.content.match(/\{\{(\w+)\}\}/g) || [];
      const variables = [...new Set(variableMatches.map(v => v.replace(/\{\{|\}\}/g, '')))];

      const templateData = {
        ...formData,
        variables
      };

      if (editingTemplate) {
        await api.put(`/api/templates/${editingTemplate.id}`, templateData);
        showAlert('success', 'Template updated successfully');
      } else {
        await api.post('/api/templates/', templateData);
        showAlert('success', 'Template created successfully');
      }

      setShowModal(false);
      resetForm();
      loadTemplates();
    } catch (error) {
      showAlert('error', error.response?.data?.detail || 'Failed to save template');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (templateId) => {
    if (!confirm('Are you sure you want to delete this template?')) return;

    try {
      await api.delete(`/api/templates/${templateId}`);
      showAlert('success', 'Template deleted');
      loadTemplates();
    } catch (error) {
      showAlert('error', 'Failed to delete template');
    }
  };

  const handleEdit = (template) => {
    setEditingTemplate(template);
    setFormData({
      name: template.name,
      description: template.description || '',
      content: template.content,
      variables: template.variables || [],
      is_public: template.is_public
    });
    setShowModal(true);
  };

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      content: '',
      variables: [],
      is_public: false
    });
    setEditingTemplate(null);
  };

  const showAlert = (type, message) => {
    setAlert({ type, message });
    setTimeout(() => setAlert(null), 5000);
  };

  const extractedVariables = formData.content.match(/\{\{(\w+)\}\}/g) || [];
  const uniqueVariables = [...new Set(extractedVariables.map(v => v.replace(/\{\{|\}\}/g, '')))];

  return (
    <Layout>
      <div className="container" style={{ padding: 'var(--spacing-8) var(--spacing-4)' }}>
        {alert && (
          <div style={{ marginBottom: 'var(--spacing-4)' }}>
            <Alert type={alert.type} message={alert.message} onClose={() => setAlert(null)} />
          </div>
        )}

        <div className="flex justify-between items-center" style={{ marginBottom: 'var(--spacing-8)' }}>
          <div>
            <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: '700', marginBottom: 'var(--spacing-2)' }}>
              Templates
            </h1>
            <p style={{ color: 'var(--gray-600)' }}>
              Create and manage reusable prompt templates
            </p>
          </div>
          <Button 
            variant="primary" 
            icon={Plus} 
            onClick={() => {
              resetForm();
              setShowModal(true);
            }}
          >
            New Template
          </Button>
        </div>

        {templates.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: 'var(--spacing-8)' }}>
            <FileText size={48} style={{ color: 'var(--gray-400)', margin: '0 auto var(--spacing-4)' }} />
            <p style={{ color: 'var(--gray-600)', marginBottom: 'var(--spacing-4)' }}>
              No templates yet. Create your first template to get started!
            </p>
            <Button 
              variant="primary" 
              icon={Plus} 
              onClick={() => {
                resetForm();
                setShowModal(true);
              }}
            >
              Create First Template
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-3">
            {templates.map((template) => (
              <div key={template.id} className="card">
                <div className="flex justify-between items-start" style={{ marginBottom: 'var(--spacing-4)' }}>
                  <div style={{ flex: 1 }}>
                    <h3 style={{ fontWeight: '600', marginBottom: 'var(--spacing-2)' }}>
                      {template.name}
                    </h3>
                    {template.description && (
                      <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)', marginBottom: 'var(--spacing-2)' }}>
                        {template.description}
                      </p>
                    )}
                    {template.is_public && (
                      <span className="badge badge-info" style={{ display: 'inline-flex' }}>
                        <Eye size={12} />
                        Public
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: 'var(--spacing-1)' }}>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => handleEdit(template)}
                    >
                      <Edit size={16} />
                    </button>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => handleDelete(template.id)}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>

                <div style={{ 
                  backgroundColor: 'var(--gray-50)', 
                  padding: 'var(--spacing-3)',
                  borderRadius: 'var(--radius)',
                  marginBottom: 'var(--spacing-3)'
                }}>
                  <p style={{ 
                    fontSize: 'var(--text-sm)', 
                    color: 'var(--gray-700)',
                    maxHeight: '80px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis'
                  }}>
                    {template.content.substring(0, 150)}
                    {template.content.length > 150 ? '...' : ''}
                  </p>
                </div>

                {template.variables && template.variables.length > 0 && (
                  <div>
                    <p style={{ fontSize: 'var(--text-xs)', fontWeight: '500', color: 'var(--gray-600)', marginBottom: 'var(--spacing-2)' }}>
                      Variables:
                    </p>
                    <div style={{ display: 'flex', gap: 'var(--spacing-1)', flexWrap: 'wrap' }}>
                      {template.variables.map((variable, index) => (
                        <span 
                          key={index}
                          style={{
                            fontSize: 'var(--text-xs)',
                            padding: '2px 8px',
                            backgroundColor: 'var(--primary)',
                            color: 'white',
                            borderRadius: 'var(--radius-sm)',
                            fontFamily: 'monospace'
                          }}
                        >
                          {`{{${variable}}}`}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {showModal && (
          <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: 'var(--spacing-4)'
          }}>
            <div className="card" style={{ width: '100%', maxWidth: '700px', maxHeight: '90vh', overflow: 'auto' }}>
              <h2 style={{ fontSize: 'var(--text-2xl)', fontWeight: '600', marginBottom: 'var(--spacing-6)' }}>
                {editingTemplate ? 'Edit Template' : 'New Template'}
              </h2>

              <form onSubmit={handleSubmit}>
                <div className="form-group">
                  <label className="form-label">Template Name</label>
                  <input
                    type="text"
                    className="form-input"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required
                    placeholder="e.g., Blog Post Generator"
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Description (Optional)</label>
                  <input
                    type="text"
                    className="form-input"
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Brief description of this template"
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Template Content</label>
                  <textarea
                    className="form-textarea"
                    value={formData.content}
                    onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                    required
                    rows={10}
                    placeholder="Write your template here. Use {{variable}} for dynamic values.&#10;&#10;Example:&#10;Write a blog post about {{topic}} targeting {{audience}}."
                  />
                  <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: 'var(--spacing-2)' }}>
                    Use <code style={{ backgroundColor: 'var(--gray-100)', padding: '2px 4px', borderRadius: 'var(--radius-sm)' }}>
                      {`{{variable}}`}
                    </code> syntax for dynamic values
                  </p>
                </div>

                {uniqueVariables.length > 0 && (
                  <div style={{ 
                    padding: 'var(--spacing-3)', 
                    backgroundColor: 'var(--gray-50)', 
                    borderRadius: 'var(--radius)',
                    marginBottom: 'var(--spacing-4)'
                  }}>
                    <p style={{ fontSize: 'var(--text-sm)', fontWeight: '500', marginBottom: 'var(--spacing-2)' }}>
                      Detected Variables:
                    </p>
                    <div style={{ display: 'flex', gap: 'var(--spacing-2)', flexWrap: 'wrap' }}>
                      {uniqueVariables.map((variable, index) => (
                        <span 
                          key={index}
                          style={{
                            fontSize: 'var(--text-sm)',
                            padding: '4px 8px',
                            backgroundColor: 'var(--primary)',
                            color: 'white',
                            borderRadius: 'var(--radius-sm)',
                            fontFamily: 'monospace'
                          }}
                        >
                          {`{{${variable}}}`}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div className="form-group">
                  <Toggle
                    checked={formData.is_public}
                    onChange={(checked) => setFormData({ ...formData, is_public: checked })}
                    label="Make this template public"
                  />
                  <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: 'var(--spacing-1)' }}>
                    Public templates can be seen by all users
                  </p>
                </div>

                <div style={{ display: 'flex', gap: 'var(--spacing-3)', justifyContent: 'flex-end' }}>
                  <Button 
                    variant="ghost" 
                    onClick={() => {
                      setShowModal(false);
                      resetForm();
                    }}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" variant="primary" loading={loading}>
                    {editingTemplate ? 'Update Template' : 'Create Template'}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Templates;