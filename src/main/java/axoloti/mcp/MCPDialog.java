package axoloti.mcp;

import axoloti.MainFrame;
import axoloti.PatchFrame;
import axoloti.PatchGUI;
import axoloti.Theme;
import java.awt.BorderLayout;
import java.awt.Dimension;
import java.awt.FlowLayout;
import java.awt.Frame;
import java.awt.GridBagConstraints;
import java.awt.GridBagLayout;
import java.awt.Insets;
import java.awt.event.ActionEvent;
import javax.swing.BorderFactory;
import javax.swing.Box;
import javax.swing.JButton;
import javax.swing.JCheckBox;
import javax.swing.JDialog;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JScrollPane;
import javax.swing.JTextArea;
import javax.swing.SwingWorker;

/**
 * Dialog for entering natural language descriptions to generate patches
 */
public class MCPDialog extends JDialog {
    private final JTextArea descriptionArea;
    private final JButton generateButton;
    private final JCheckBox useGillsCheckbox;
    private NLPPatchGenerator patchGenerator;
    
    public MCPDialog(Frame owner) {
        super(owner, "Generate Patch with Natural Language", true);
        this.patchGenerator = new NLPPatchGenerator();
        
        // Create UI components
        JPanel mainPanel = new JPanel(new BorderLayout(10, 10));
        mainPanel.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10));
        
        JLabel instructionLabel = new JLabel("<html>Describe the patch you want to create:<br/>" +
                "Be as specific as possible about sounds, connections, and parameters.</html>");
        mainPanel.add(instructionLabel, BorderLayout.NORTH);
        
        descriptionArea = new JTextArea(10, 40);
        descriptionArea.setLineWrap(true);
        descriptionArea.setWrapStyleWord(true);
        descriptionArea.setFont(descriptionArea.getFont().deriveFont(14f));
        
        JScrollPane scrollPane = new JScrollPane(descriptionArea);
        scrollPane.setVerticalScrollBarPolicy(JScrollPane.VERTICAL_SCROLLBAR_ALWAYS);
        mainPanel.add(scrollPane, BorderLayout.CENTER);
        
        // Add options panel between text area and buttons
        JPanel optionsPanel = new JPanel(new GridBagLayout());
        GridBagConstraints gbc = new GridBagConstraints();
        gbc.gridx = 0;
        gbc.gridy = 0;
        gbc.anchor = GridBagConstraints.WEST;
        gbc.insets = new Insets(5, 0, 5, 0);
        
        // Add Gills hardware checkbox
        useGillsCheckbox = new JCheckBox("Use Ksoloti Gills hardware controls");
        useGillsCheckbox.setToolTipText("Create a patch that uses physical controls from the Gills expansion board");
        optionsPanel.add(useGillsCheckbox, gbc);
        
        // Add options panel to main panel
        mainPanel.add(optionsPanel, BorderLayout.SOUTH);
        
        // Create button panel
        JPanel buttonPanel = new JPanel();
        buttonPanel.setLayout(new BorderLayout());
        
        // Left buttons panel
        JPanel leftButtonPanel = new JPanel(new FlowLayout(FlowLayout.LEFT));
        
        // Add examples button
        JButton examplesButton = new JButton("Show Examples");
        examplesButton.addActionListener(this::onExamplesClicked);
        leftButtonPanel.add(examplesButton);
        
        // Add settings button
        JButton settingsButton = new JButton("Settings");
        settingsButton.addActionListener(this::onSettingsClicked);
        leftButtonPanel.add(settingsButton);
        
        buttonPanel.add(leftButtonPanel, BorderLayout.WEST);
        
        // Right buttons panel for generate button
        JPanel rightButtonPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT));
        
        // Add generate button 
        generateButton = new JButton("Generate Patch");
        generateButton.addActionListener(this::onGenerateClicked);
        rightButtonPanel.add(generateButton);
        
        buttonPanel.add(rightButtonPanel, BorderLayout.EAST);
        
        // Add button panel at the very bottom
        optionsPanel.add(buttonPanel, gbc);
        
        setContentPane(mainPanel);
        pack();
        setLocationRelativeTo(owner);
        setMinimumSize(new Dimension(500, 300));
    }
    
    private void onExamplesClicked(ActionEvent e) {
        // Show different examples based on whether Gills is enabled
        if (useGillsCheckbox.isSelected()) {
            JOptionPane.showMessageDialog(this,
                    "<html><b>Example prompts with Gills hardware:</b><br/><br/>" +
                    "- Create a synth with 3 pots controlling oscillator pitch, filter cutoff, and reverb amount<br/>" +
                    "- Make a drum machine with buttons to trigger sounds and LEDs showing beat position<br/>" +
                    "- Build a synth with a pot to control cutoff and one for resonance<br/>" +
                    "- Create a wavetable oscillator where pot 1 controls pitch and pot 2 selects wave shape<br/>" +
                    "- Make an FM synth with pots for carrier, modulator and index with OLED display feedback</html>",
                    "Example Descriptions with Gills",
                    JOptionPane.INFORMATION_MESSAGE);
        } else {
            JOptionPane.showMessageDialog(this,
                    "<html><b>Example prompts:</b><br/><br/>" +
                    "- Create a simple sine wave oscillator with volume control<br/>" +
                    "- Make a drum machine with kick and snare<br/>" +
                    "- Build a subtractive synth with two oscillators, a filter, and an envelope<br/>" +
                    "- Create an ambient pad with reverb and delay<br/>" +
                    "- Make a sequencer that controls a bass synth</html>",
                    "Example Descriptions",
                    JOptionPane.INFORMATION_MESSAGE);
        }
    }
    
    /**
     * Check if the Gemini API key is configured and return a warning message if not
     */
    private boolean isGeminiApiConfigured() {
        return !LLMServiceGemini.getApiKey().isEmpty();
    }
    
    private void onGenerateClicked(ActionEvent e) {
        String description = descriptionArea.getText().trim();
        if (description.isEmpty()) {
            JOptionPane.showMessageDialog(this, 
                    "Please enter a description of the patch you want to create.",
                    "Empty Description", 
                    JOptionPane.WARNING_MESSAGE);
            return;
        }
        
        // Check if Gemini API is configured
        if (!isGeminiApiConfigured()) {
            int result = JOptionPane.showConfirmDialog(this,
                    "No Gemini API key configured. The patcher will use the mock implementation with limited capabilities.\n" +
                    "Would you like to configure the Gemini API key now?",
                    "API Key Not Configured",
                    JOptionPane.YES_NO_CANCEL_OPTION,
                    JOptionPane.QUESTION_MESSAGE);
            
            if (result == JOptionPane.YES_OPTION) {
                // Open settings dialog
                MCPSettingsDialog settingsDialog = new MCPSettingsDialog((Frame)this.getOwner());
                settingsDialog.setVisible(true);
                
                // Recreate the patchGenerator to pick up any API key changes
                this.patchGenerator = new NLPPatchGenerator();
                
                // If still not configured, cancel the operation
                if (!isGeminiApiConfigured()) {
                    return;
                }
            } else if (result == JOptionPane.CANCEL_OPTION) {
                return;
            }
            // For NO_OPTION, continue with mock implementation
        }
        
        // Enhance the description if Gills hardware is explicitly selected
        if (useGillsCheckbox.isSelected()) {
            // Only add the Gills prefix if it's not already mentioned
            if (!description.toLowerCase().contains("gills")) {
                description = "Using Ksoloti Gills hardware controls for: " + description;
            }
        }
        
        // Show processing indication
        generateButton.setEnabled(false);
        generateButton.setText("Generating...");
        
        // Store final description for worker thread
        final String finalDescription = description;
        
        // Process in background thread
        SwingWorker<PatchGUI, Void> worker = new SwingWorker<PatchGUI, Void>() {
            @Override
            protected PatchGUI doInBackground() throws Exception {
                // Generate patch
                return patchGenerator.generatePatch(finalDescription);
            }
            
            @Override
            protected void done() {
                try {
                    PatchGUI patch = get();
                    if (patch != null) {
                        // Must set filename/filepath here, not in generatePatch
                        String fileName = "generated_" + System.currentTimeMillis();
                        
                        // Create a PatchFrame and initialize it properly
                        // This needs to be done before calling setFileNamePath
                        PatchFrame pf = new PatchFrame(patch, MainFrame.mainframe.getQcmdprocessor());
                        
                        // Now it's safe to call setFileNamePath
                        patch.setFileNamePath(fileName);
                        
                        // Now call PostContructor after PatchFrame is created
                        patch.PostContructor();
                        
                        // Show the patch frame
                        pf.setVisible(true);
                        
                        // Close dialog
                        dispose();
                    } else {
                        throw new Exception("Failed to generate patch");
                    }
                } catch (Exception ex) {
                    JOptionPane.showMessageDialog(MCPDialog.this, 
                                                "Error generating patch: " + ex.getMessage(),
                                                "Generation Error", 
                                                JOptionPane.ERROR_MESSAGE);
                    generateButton.setEnabled(true);
                    generateButton.setText("Generate Patch");
                }
            }
        };
        worker.execute();
    }
    
    private void onSettingsClicked(ActionEvent e) {
        MCPSettingsDialog settingsDialog = new MCPSettingsDialog((Frame)this.getOwner());
        settingsDialog.setVisible(true);
        
        // Recreate the patchGenerator to pick up any API key changes
        this.patchGenerator = new NLPPatchGenerator();
    }
} 