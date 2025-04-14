package axoloti.mcp;

import java.util.logging.Logger;

/**
 * Mock implementation of the LLM service for testing
 * Provides predefined responses for different inputs
 */
public class LLMServiceMock implements LLMService {
    private static final Logger LOGGER = Logger.getLogger(LLMServiceMock.class.getName());
    
    @Override
    public String generatePatchSpecification(String description) {
        LOGGER.info("Mock LLM service processing: " + description);
        
        // Simple oscillator patch for testing
        if (description.toLowerCase().contains("oscillator") || description.toLowerCase().contains("sine")) {
            return createOscillatorPatch();
        }
        
        // Simple drum machine patch for testing
        if (description.toLowerCase().contains("drum") || description.toLowerCase().contains("beat")) {
            return createDrumPatch();
        }
        
        // Default to a simple patch if no specific match
        return createDefaultPatch();
    }
    
    private String createOscillatorPatch() {
        return "{" +
                "\"name\": \"Simple Oscillator\"," +
                "\"description\": \"A simple sine wave oscillator with volume control\"," +
                "\"objects\": [" +
                "  {" +
                "    \"id\": \"osc1\"," +
                "    \"type\": \"osc/sine\"," +
                "    \"x\": 100," +
                "    \"y\": 100," +
                "    \"parameters\": {" +
                "      \"pitch\": \"440.0\"" +
                "    }" +
                "  }," +
                "  {" +
                "    \"id\": \"gain1\"," +
                "    \"type\": \"gain/vca\"," +
                "    \"x\": 300," +
                "    \"y\": 100," +
                "    \"parameters\": {" +
                "      \"gain\": \"0.5\"" +
                "    }" +
                "  }," +
                "  {" +
                "    \"id\": \"out1\"," +
                "    \"type\": \"audio/out stereo\"," +
                "    \"x\": 500," +
                "    \"y\": 100" +
                "  }" +
                "]," +
                "\"connections\": [" +
                "  {" +
                "    \"sourceObjectId\": \"osc1\"," +
                "    \"sourceOutlet\": \"out\"," +
                "    \"destObjectId\": \"gain1\"," +
                "    \"destInlet\": \"in\"" +
                "  }," +
                "  {" +
                "    \"sourceObjectId\": \"gain1\"," +
                "    \"sourceOutlet\": \"out\"," +
                "    \"destObjectId\": \"out1\"," +
                "    \"destInlet\": \"left\"" +
                "  }," +
                "  {" +
                "    \"sourceObjectId\": \"gain1\"," +
                "    \"sourceOutlet\": \"out\"," +
                "    \"destObjectId\": \"out1\"," +
                "    \"destInlet\": \"right\"" +
                "  }" +
                "]" +
                "}";
    }
    
    private String createDrumPatch() {
        return "{" +
                "\"name\": \"Simple Drum Machine\"," +
                "\"description\": \"A basic drum machine with kick and snare\"," +
                "\"objects\": [" +
                "  {" +
                "    \"id\": \"clock1\"," +
                "    \"type\": \"pulse/bpm\"," +
                "    \"x\": 50," +
                "    \"y\": 50," +
                "    \"parameters\": {" +
                "      \"bpm\": \"120\"" +
                "    }" +
                "  }," +
                "  {" +
                "    \"id\": \"kick1\"," +
                "    \"type\": \"drum/kick\"," +
                "    \"x\": 200," +
                "    \"y\": 50" +
                "  }," +
                "  {" +
                "    \"id\": \"snare1\"," +
                "    \"type\": \"drum/snare\"," +
                "    \"x\": 200," +
                "    \"y\": 150" +
                "  }," +
                "  {" +
                "    \"id\": \"mix1\"," +
                "    \"type\": \"mix/stereo 2\"," +
                "    \"x\": 350," +
                "    \"y\": 100" +
                "  }," +
                "  {" +
                "    \"id\": \"out1\"," +
                "    \"type\": \"audio/out stereo\"," +
                "    \"x\": 500," +
                "    \"y\": 100" +
                "  }" +
                "]," +
                "\"connections\": [" +
                "  {" +
                "    \"sourceObjectId\": \"clock1\"," +
                "    \"sourceOutlet\": \"trig\"," +
                "    \"destObjectId\": \"kick1\"," +
                "    \"destInlet\": \"trig\"" +
                "  }," +
                "  {" +
                "    \"sourceObjectId\": \"clock1\"," +
                "    \"sourceOutlet\": \"div2\"," +
                "    \"destObjectId\": \"snare1\"," +
                "    \"destInlet\": \"trig\"" +
                "  }," +
                "  {" +
                "    \"sourceObjectId\": \"kick1\"," +
                "    \"sourceOutlet\": \"out\"," +
                "    \"destObjectId\": \"mix1\"," +
                "    \"destInlet\": \"in1\"" +
                "  }," +
                "  {" +
                "    \"sourceObjectId\": \"snare1\"," +
                "    \"sourceOutlet\": \"out\"," +
                "    \"destObjectId\": \"mix1\"," +
                "    \"destInlet\": \"in2\"" +
                "  }," +
                "  {" +
                "    \"sourceObjectId\": \"mix1\"," +
                "    \"sourceOutlet\": \"out\"," +
                "    \"destObjectId\": \"out1\"," +
                "    \"destInlet\": \"left\"" +
                "  }," +
                "  {" +
                "    \"sourceObjectId\": \"mix1\"," +
                "    \"sourceOutlet\": \"out\"," +
                "    \"destObjectId\": \"out1\"," +
                "    \"destInlet\": \"right\"" +
                "  }" +
                "]" +
                "}";
    }
    
    private String createDefaultPatch() {
        return "{" +
                "\"name\": \"Default Patch\"," +
                "\"description\": \"A simple gain and output\"," +
                "\"objects\": [" +
                "  {" +
                "    \"id\": \"gain1\"," +
                "    \"type\": \"gain/vca\"," +
                "    \"x\": 200," +
                "    \"y\": 100," +
                "    \"parameters\": {" +
                "      \"gain\": \"0.5\"" +
                "    }" +
                "  }," +
                "  {" +
                "    \"id\": \"out1\"," +
                "    \"type\": \"audio/out stereo\"," +
                "    \"x\": 400," +
                "    \"y\": 100" +
                "  }" +
                "]," +
                "\"connections\": [" +
                "  {" +
                "    \"sourceObjectId\": \"gain1\"," +
                "    \"sourceOutlet\": \"out\"," +
                "    \"destObjectId\": \"out1\"," +
                "    \"destInlet\": \"left\"" +
                "  }," +
                "  {" +
                "    \"sourceObjectId\": \"gain1\"," +
                "    \"sourceOutlet\": \"out\"," +
                "    \"destObjectId\": \"out1\"," +
                "    \"destInlet\": \"right\"" +
                "  }" +
                "]" +
                "}";
    }
} 