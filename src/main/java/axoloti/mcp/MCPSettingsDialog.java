package axoloti.mcp;

import java.awt.BorderLayout;
import java.awt.Dimension;
import java.awt.FlowLayout;
import java.awt.Frame;
import java.awt.GridBagConstraints;
import java.awt.GridBagLayout;
import java.awt.Insets;
import java.awt.event.ActionEvent;
import javax.swing.BorderFactory;
import javax.swing.JButton;
import javax.swing.JDialog;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JPasswordField;
import javax.swing.JTabbedPane;
import javax.swing.JTextField;

/**
 * Settings dialog for MCP configuration
 */
public class MCPSettingsDialog extends JDialog {
    
    private JTextField apiKeyField;
    
    public MCPSettingsDialog(Frame owner) {
        super(owner, "MCP Settings", true);
        
        // Create UI
        JPanel mainPanel = new JPanel(new BorderLayout(10, 10));
        mainPanel.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10));
        
        JTabbedPane tabbedPane = new JTabbedPane();
        
        // API Settings panel
        JPanel apiPanel = createApiPanel();
        tabbedPane.addTab("LLM API Settings", apiPanel);
        
        mainPanel.add(tabbedPane, BorderLayout.CENTER);
        
        // Buttons panel
        JPanel buttonPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT));
        JButton cancelButton = new JButton("Cancel");
        JButton saveButton = new JButton("Save");
        
        cancelButton.addActionListener(this::onCancelClicked);
        saveButton.addActionListener(this::onSaveClicked);
        
        buttonPanel.add(cancelButton);
        buttonPanel.add(saveButton);
        mainPanel.add(buttonPanel, BorderLayout.SOUTH);
        
        setContentPane(mainPanel);
        pack();
        setLocationRelativeTo(owner);
        setMinimumSize(new Dimension(400, 250));
    }
    
    private JPanel createApiPanel() {
        JPanel panel = new JPanel(new GridBagLayout());
        panel.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10));
        
        GridBagConstraints gbc = new GridBagConstraints();
        gbc.gridx = 0;
        gbc.gridy = 0;
        gbc.anchor = GridBagConstraints.WEST;
        gbc.insets = new Insets(5, 5, 5, 5);
        
        // Model selection (for future use with multiple models)
        JLabel modelLabel = new JLabel("LLM Model:");
        panel.add(modelLabel, gbc);
        
        gbc.gridx = 1;
        gbc.fill = GridBagConstraints.HORIZONTAL;
        gbc.weightx = 1.0;
        
        JLabel modelValueLabel = new JLabel("Google Gemini 1.5 Flash");
        panel.add(modelValueLabel, gbc);
        
        // API Key
        gbc.gridx = 0;
        gbc.gridy = 1;
        gbc.weightx = 0;
        gbc.fill = GridBagConstraints.NONE;
        
        JLabel apiKeyLabel = new JLabel("API Key:");
        panel.add(apiKeyLabel, gbc);
        
        gbc.gridx = 1;
        gbc.fill = GridBagConstraints.HORIZONTAL;
        gbc.weightx = 1.0;
        
        apiKeyField = new JPasswordField(LLMServiceGemini.getApiKey());
        panel.add(apiKeyField, gbc);
        
        // Instructions
        gbc.gridx = 0;
        gbc.gridy = 2;
        gbc.gridwidth = 2;
        gbc.insets = new Insets(20, 5, 5, 5);
        
        JLabel instructionsLabel = new JLabel("<html>" +
                "To use Gemini, you need to obtain an API key from Google AI Studio.<br><br>" +
                "1. Visit <a href='https://aistudio.google.com/'>https://aistudio.google.com/</a><br>" +
                "2. Create or log in to your Google account<br>" +
                "3. Navigate to API keys and create a new key<br>" +
                "4. Copy and paste the key here<br><br>" +
                "Note: Your API key will be stored in your local preferences." +
                "</html>");
        panel.add(instructionsLabel, gbc);
        
        // Fill remaining space
        gbc.gridy = 3;
        gbc.weighty = 1.0;
        panel.add(new JLabel(), gbc);
        
        return panel;
    }
    
    private void onCancelClicked(ActionEvent e) {
        dispose();
    }
    
    private void onSaveClicked(ActionEvent e) {
        String apiKey = apiKeyField.getText().trim();
        
        // Validate API key (basic validation - not empty)
        if (apiKey.isEmpty()) {
            JOptionPane.showMessageDialog(this,
                    "Please enter a valid API key.",
                    "Invalid API Key",
                    JOptionPane.WARNING_MESSAGE);
            return;
        }
        
        // Save API key
        LLMServiceGemini.saveApiKey(apiKey);
        
        JOptionPane.showMessageDialog(this,
                "Settings saved successfully.",
                "Settings Saved",
                JOptionPane.INFORMATION_MESSAGE);
        
        dispose();
    }
} 