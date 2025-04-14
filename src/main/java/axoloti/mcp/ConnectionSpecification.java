package axoloti.mcp;

/**
 * Represents a specification for a connection between two objects in a patch
 */
public class ConnectionSpecification {
    private String sourceObjectId;
    private String sourceOutlet;
    private String destObjectId;
    private String destInlet;
    
    public ConnectionSpecification() {
    }
    
    public String getSourceObjectId() {
        return sourceObjectId;
    }
    
    public void setSourceObjectId(String sourceObjectId) {
        this.sourceObjectId = sourceObjectId;
    }
    
    public String getSourceOutlet() {
        return sourceOutlet;
    }
    
    public void setSourceOutlet(String sourceOutlet) {
        this.sourceOutlet = sourceOutlet;
    }
    
    public String getDestObjectId() {
        return destObjectId;
    }
    
    public void setDestObjectId(String destObjectId) {
        this.destObjectId = destObjectId;
    }
    
    public String getDestInlet() {
        return destInlet;
    }
    
    public void setDestInlet(String destInlet) {
        this.destInlet = destInlet;
    }
    
    @Override
    public String toString() {
        return "ConnectionSpecification{" +
                "sourceObjectId='" + sourceObjectId + '\'' +
                ", sourceOutlet='" + sourceOutlet + '\'' +
                ", destObjectId='" + destObjectId + '\'' +
                ", destInlet='" + destInlet + '\'' +
                '}';
    }
} 